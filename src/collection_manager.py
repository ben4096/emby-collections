"""
Collection Manager
Manages the creation and updating of Emby collections based on external lists
"""

import logging
from typing import List, Dict, Set, Optional, Tuple
from emby_client import EmbyClient


class CollectionManager:
    """Manages Emby collections based on external movie lists"""

    def __init__(self, emby_client: EmbyClient, match_priority: List[str] = None,
                 remove_missing: bool = True, dry_run: bool = False, clear_collections: bool = False,
                 delete_unlisted: bool = False):
        """
        Initialize Collection Manager

        Args:
            emby_client: EmbyClient instance
            match_priority: Priority order for matching (e.g., ['imdb_id', 'tmdb_id', 'title'])
            remove_missing: Remove items from collection if not in source list
            dry_run: If True, don't actually modify collections
            clear_collections: If True, clear all items from existing collections before syncing
            delete_unlisted: If True, delete collections not in the managed list
        """
        self.emby = emby_client
        self.match_priority = match_priority or ['imdb_id', 'tmdb_id', 'title']
        self.remove_missing = remove_missing
        self.dry_run = dry_run
        self.clear_collections = clear_collections
        self.delete_unlisted = delete_unlisted
        self.logger = logging.getLogger(__name__)
        self.managed_collection_names = set()  # Track which collections we manage

    def sync_collection(self, collection_name: str, movies: List[Dict], overview: str = None,
                       image_path: str = None, display_order: str = None, sort_title: str = None) -> Dict[str, int]:
        """
        Sync a collection with a list of movies

        Args:
            collection_name: Name of the collection to create/update
            movies: List of movie dicts from external source
            overview: Optional description/overview for the collection
            image_path: Optional path to image file for the collection
            display_order: Optional display order metadata ("PremiereDate" or "SortName")
            sort_title: Optional sort title for custom collection ordering

        Returns:
            Dict with stats: {'added': int, 'removed': int, 'total': int, 'not_found': int}
        """
        # Track this as a managed collection
        self.managed_collection_names.add(collection_name)

        stats = {
            'added': 0,
            'removed': 0,
            'total': len(movies),
            'not_found': 0,
            'already_present': 0
        }

        self.logger.info(f"Syncing collection '{collection_name}' with {len(movies)} movies")

        # Sort movies by list_rank if available (maintains Trakt list order)
        if movies and 'list_rank' in movies[0]:
            movies = sorted(movies, key=lambda x: x.get('list_rank', 9999))
            self.logger.debug(f"Sorted movies by list rank")

        # Match movies to Emby library items
        matched_item_ids, not_found = self._match_movies_to_library(movies)

        stats['not_found'] = len(not_found)

        if not_found:
            self.logger.warning(f"{len(not_found)} movies not found in library:")
            for movie in not_found[:10]:  # Show first 10
                self.logger.warning(f"  - {movie.get('title')} ({movie.get('year', 'N/A')})")
            if len(not_found) > 10:
                self.logger.warning(f"  ... and {len(not_found) - 10} more")

        if not matched_item_ids:
            self.logger.warning(f"No movies matched in library for collection '{collection_name}'")
            return stats

        # Check if collection exists
        existing_collections = self.emby.get_collections(name=collection_name)

        if existing_collections:
            collection = existing_collections[0]
            collection_id = collection['Id']
            self.logger.info(f"Collection '{collection_name}' already exists (ID: {collection_id})")

            # Update metadata if provided
            if overview or sort_title:
                self.emby.update_collection_metadata(collection_id, overview=overview, sort_name=sort_title)
            if display_order:
                self.emby.update_collection_display_order(collection_id, display_order)

            # Update image if provided
            if image_path:
                self._set_collection_image(collection_id, image_path)

            # Clear collection if requested
            if self.clear_collections:
                cleared = self._clear_collection(collection_id)
                if cleared:
                    # After clearing, all desired items need to be added
                    if self.dry_run:
                        self.logger.info(f"[DRY RUN] Would add {len(matched_item_ids)} items to cleared collection")
                        stats['added'] = len(matched_item_ids)
                        stats['removed'] = 0
                        stats['already_present'] = 0
                    else:
                        self.emby.add_to_collection(collection_id, matched_item_ids)
                        stats['added'] = len(matched_item_ids)
                        stats['removed'] = 0
                        stats['already_present'] = 0
                        self.logger.info(f"Added {len(matched_item_ids)} items to cleared collection")
                else:
                    # Clear failed, fall back to normal update
                    added, removed, already_present = self._update_collection(
                        collection_id, matched_item_ids
                    )
                    stats['added'] = added
                    stats['removed'] = removed
                    stats['already_present'] = already_present
            else:
                # Normal update without clearing
                added, removed, already_present = self._update_collection(
                    collection_id, matched_item_ids
                )
                stats['added'] = added
                stats['removed'] = removed
                stats['already_present'] = already_present
        else:
            # Create new collection
            if self.dry_run:
                self.logger.info(f"[DRY RUN] Would create collection '{collection_name}' with {len(matched_item_ids)} items")
                if overview:
                    self.logger.info(f"[DRY RUN] Would set overview: {overview}")
                if image_path:
                    self.logger.info(f"[DRY RUN] Would set image: {image_path}")
                stats['added'] = len(matched_item_ids)
            else:
                try:
                    result = self.emby.create_collection(
                        collection_name,
                        matched_item_ids,
                        overview=overview,
                        display_order=display_order,
                        sort_name=sort_title
                    )
                    stats['added'] = len(matched_item_ids)
                    self.logger.info(f"Created new collection '{collection_name}' with {len(matched_item_ids)} items")

                    # Set image if provided
                    if result:
                        collection_id = result.get('Id')
                        if collection_id and image_path:
                            self._set_collection_image(collection_id, image_path)
                except Exception as e:
                    self.logger.error(f"Failed to create collection '{collection_name}': {e}")

        return stats

    def _match_movies_to_library(self, movies: List[Dict]) -> Tuple[List[str], List[Dict]]:
        """
        Match movies from external list to Emby library items

        Args:
            movies: List of movie dicts with external IDs

        Returns:
            Tuple of (matched_item_ids, not_found_movies)
        """
        matched_ids = []
        not_found = []

        for movie in movies:
            item = self._find_movie_in_library(movie)

            if item:
                matched_ids.append(item['Id'])
                self.logger.debug(f"Matched: {movie.get('title')} -> {item.get('Name')} (ID: {item['Id']})")
            else:
                not_found.append(movie)

        self.logger.info(f"Matched {len(matched_ids)}/{len(movies)} movies in library")
        return matched_ids, not_found

    def _find_movie_in_library(self, movie: Dict) -> Optional[Dict]:
        """
        Find a single movie in Emby library using configured match priority

        Args:
            movie: Movie dict with IDs and metadata

        Returns:
            Emby item dict or None
        """
        # Try each matching strategy in priority order
        for strategy in self.match_priority:
            if strategy == 'imdb_id' and movie.get('imdb_id'):
                items = self.emby.search_items(imdb_id=movie['imdb_id'])
                if items:
                    # Should only be one match for IMDb ID
                    if len(items) > 1:
                        self.logger.warning(f"Multiple matches for IMDb {movie['imdb_id']}: {[i.get('Name') for i in items]}")
                    item = items[0]
                    # Verify the match
                    item_imdb = item.get('ProviderIds', {}).get('Imdb', '')
                    if item_imdb != movie['imdb_id']:
                        self.logger.error(f"IMDb ID mismatch! Searched: {movie['imdb_id']}, Got: {item_imdb} for '{item.get('Name')}'")
                        self.logger.error(f"This is a bug in matching - skipping '{movie.get('title')}'")
                        continue
                    return item

            elif strategy == 'tmdb_id' and movie.get('tmdb_id'):
                items = self.emby.search_items(tmdb_id=movie['tmdb_id'])
                if items:
                    if len(items) > 1:
                        self.logger.warning(f"Multiple matches for TMDb {movie['tmdb_id']}: {[i.get('Name') for i in items]}")
                    return items[0]

            elif strategy == 'title' and movie.get('title'):
                # Search by title (less reliable - ONLY use if we have a year to verify)
                if not movie.get('year'):
                    # Skip title matching if we don't have a year - too unreliable
                    self.logger.debug(f"Skipping title match for '{movie['title']}' - no year available")
                    continue

                items = self.emby.search_items(search_term=movie['title'])

                # ONLY match if we have a year AND it matches exactly
                if items and movie.get('year'):
                    for item in items:
                        item_year = item.get('ProductionYear')
                        if item_year and str(item_year) == str(movie['year']):
                            # Additional sanity check: titles should be very similar
                            movie_title_lower = movie['title'].lower().strip()
                            item_title_lower = item.get('Name', '').lower().strip()

                            # Only match if titles are identical or very close
                            # Require at least 80% of the words to match to avoid false positives like "Love" matching "Love the Coopers"
                            movie_words = set(movie_title_lower.split())
                            item_words = set(item_title_lower.split())

                            if movie_words and item_words:
                                common_words = movie_words & item_words
                                # Calculate similarity from both perspectives to avoid "Love" matching "Love the Coopers"
                                movie_coverage = len(common_words) / len(movie_words)
                                item_coverage = len(common_words) / len(item_words)

                                # BOTH titles must have at least 80% of their words in common
                                # This prevents short titles from matching longer titles
                                if movie_coverage >= 0.8 and item_coverage >= 0.8:
                                    return item
                                else:
                                    self.logger.debug(f"Skipping title match - titles not similar enough (coverage: {movie_coverage:.0%}/{item_coverage:.0%}): '{movie['title']}' vs '{item.get('Name')}'")
                            else:
                                self.logger.debug(f"Skipping title match - empty title: '{movie['title']}' vs '{item.get('Name')}'")

                # DO NOT return first match if no exact year+title match

        return None

    def _update_collection(self, collection_id: str, desired_item_ids: List[str]) -> Tuple[int, int, int]:
        """
        Update an existing collection with desired items
        Note: This clears and rebuilds to maintain correct order

        Args:
            collection_id: Collection ID
            desired_item_ids: List of item IDs that should be in collection (in order)

        Returns:
            Tuple of (added_count, removed_count, already_present_count)
        """
        # Get current items in collection
        current_items = self.emby.get_collection_items(collection_id)
        current_item_ids = {item['Id'] for item in current_items}
        desired_item_ids_set = set(desired_item_ids)

        # Check if anything changed
        items_changed = current_item_ids != desired_item_ids_set

        # Check if order might have changed (if same items but different order)
        order_might_differ = (current_item_ids == desired_item_ids_set and
                             len(current_items) == len(desired_item_ids))

        if not items_changed and not order_might_differ:
            # Nothing changed
            self.logger.info(f"Collection already up to date")
            return 0, 0, len(desired_item_ids)

        # To preserve order, we need to clear and rebuild the collection
        # This is the only reliable way to maintain order in Emby
        if self.dry_run:
            to_add = list(desired_item_ids_set - current_item_ids)
            to_remove = list(current_item_ids - desired_item_ids_set) if self.remove_missing else []
            already_present = len(desired_item_ids_set & current_item_ids)

            if items_changed:
                self.logger.info(f"[DRY RUN] Would rebuild collection to maintain order")
                self.logger.info(f"[DRY RUN] Changes: {len(to_add)} new, {len(to_remove)} removed, {already_present} staying")
            else:
                self.logger.info(f"[DRY RUN] Would rebuild collection to fix order (same items)")

            return len(to_add), len(to_remove), already_present
        else:
            # Clear and rebuild to maintain order
            self.logger.info(f"Rebuilding collection to maintain correct order...")
            self.emby.remove_from_collection(collection_id, list(current_item_ids))
            self.emby.add_to_collection(collection_id, desired_item_ids)

            added = len(desired_item_ids_set - current_item_ids)
            removed = len(current_item_ids - desired_item_ids_set)
            stayed = len(desired_item_ids_set & current_item_ids)

            self.logger.info(f"Collection rebuilt: {added} new, {removed} removed, {stayed} reordered")
            return added, removed, stayed

    def _clear_collection(self, collection_id: str) -> bool:
        """
        Clear all items from a collection (does NOT delete the movies/shows themselves)

        Args:
            collection_id: Collection ID to clear

        Returns:
            True if successful
        """
        current_items = self.emby.get_collection_items(collection_id)

        if not current_items:
            self.logger.info(f"Collection {collection_id} is already empty")
            return True

        current_item_ids = [item['Id'] for item in current_items]

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would clear {len(current_item_ids)} items from collection {collection_id}")
            return True

        self.logger.info(f"Clearing {len(current_item_ids)} items from collection (movies themselves are NOT deleted)")
        return self.emby.remove_from_collection(collection_id, current_item_ids)

    def delete_unlisted_collections(self) -> int:
        """
        Delete collections that are not in the managed list
        WARNING: This deletes the collection itself (but NOT the movies/shows)

        Returns:
            Number of collections deleted
        """
        if not self.delete_unlisted:
            return 0

        # Get all collections from Emby
        all_collections = self.emby.get_collections()

        deleted_count = 0
        for collection in all_collections:
            collection_name = collection.get('Name', '')
            collection_id = collection.get('Id', '')

            # If this collection is not in our managed list, delete it
            if collection_name not in self.managed_collection_names:
                if self.dry_run:
                    self.logger.info(f"[DRY RUN] Would delete unlisted collection: '{collection_name}' (ID: {collection_id})")
                    deleted_count += 1
                else:
                    self.logger.warning(f"Deleting unlisted collection: '{collection_name}' (ID: {collection_id})")
                    if self.emby.delete_collection(collection_id):
                        deleted_count += 1

        if deleted_count > 0:
            self.logger.info(f"Deleted {deleted_count} unlisted collections")
        else:
            self.logger.info("No unlisted collections to delete")

        return deleted_count

    def hide_collection(self, collection_name: str) -> bool:
        """
        Hide a collection by deleting it (only the collection, NOT the movies/shows)
        Used for seasonal collections that are out of season

        Args:
            collection_name: Name of collection to hide

        Returns:
            True if successfully hidden/deleted
        """
        collections = self.emby.get_collections(name=collection_name)

        if not collections:
            self.logger.debug(f"Collection '{collection_name}' doesn't exist, nothing to hide")
            return True

        collection = collections[0]
        collection_id = collection['Id']

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would hide (delete) collection '{collection_name}' (ID: {collection_id})")
            return True
        else:
            self.logger.info(f"Hiding collection '{collection_name}' (ID: {collection_id})")
            return self.emby.delete_collection(collection_id)

    def get_collection_stats(self, collection_name: str) -> Optional[Dict]:
        """
        Get statistics about a collection

        Args:
            collection_name: Collection name

        Returns:
            Dict with collection stats or None if not found
        """
        collections = self.emby.get_collections(name=collection_name)

        if not collections:
            return None

        collection = collections[0]
        items = self.emby.get_collection_items(collection['Id'])

        return {
            'name': collection['Name'],
            'id': collection['Id'],
            'item_count': len(items),
            'created': collection.get('DateCreated'),
            'modified': collection.get('DateModified')
        }

    def _set_collection_image(self, collection_id: str, image_path: str, force: bool = False) -> bool:
        """
        Set image for a collection

        Args:
            collection_id: Collection ID
            image_path: Path to image file
            force: If True, overwrite existing image. If False, preserve manual edits.

        Returns:
            True if successful
        """
        import os

        # Make path absolute if it's relative
        if not os.path.isabs(image_path):
            # Try relative to current working directory
            abs_path = os.path.abspath(image_path)
            if not os.path.exists(abs_path):
                self.logger.error(f"Image file not found: {image_path} (tried {abs_path})")
                return False
            image_path = abs_path

        # Check if collection already has a custom image (preserve manual edits)
        if not force:
            has_image = self.emby.collection_has_custom_image(collection_id)
            if has_image:
                self.logger.debug(f"Collection {collection_id} already has a custom image, preserving it")
                return True

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would set image from {image_path}")
            return True

        return self.emby.set_collection_image(collection_id, image_path)
