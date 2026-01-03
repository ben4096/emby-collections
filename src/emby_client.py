"""
Emby API Client
Handles all interactions with the Emby server API
"""

import requests
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, quote
from metadata_tracker import MetadataTracker


class EmbyClient:
    """Client for interacting with Emby server API"""

    def __init__(self, base_url: str, api_key: str, user_id: Optional[str] = None):
        """
        Initialize Emby client

        Args:
            base_url: Emby server URL (e.g., http://localhost:8096)
            api_key: API key for authentication
            user_id: Optional user ID for user-specific operations
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'X-Emby-Token': api_key,
            'Content-Type': 'application/json'
        })

        # Metadata tracker for detecting manual edits
        self.metadata_tracker = MetadataTracker()

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Any:
        """
        Make HTTP request to Emby API

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for requests

        Returns:
            Response JSON data
        """
        url = urljoin(self.base_url, endpoint)

        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()

            # Some endpoints return empty responses
            if response.status_code == 204 or not response.content:
                return None

            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {method} {url} - {e}")
            raise

    def search_items(self, search_term: str = None, imdb_id: str = None,
                     tmdb_id: str = None, include_item_types: str = "Movie") -> List[Dict]:
        """
        Search for items in Emby library

        Args:
            search_term: Search by title
            imdb_id: Search by IMDb ID
            tmdb_id: Search by TMDb ID
            include_item_types: Item types to include (default: Movie)

        Returns:
            List of matching items
        """
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': include_item_types,
            'Fields': 'ProviderIds,ProductionYear'  # Request provider IDs to be included
        }

        if imdb_id:
            params['AnyProviderIdEquals'] = f'Imdb.{imdb_id}'
        elif tmdb_id:
            params['AnyProviderIdEquals'] = f'Tmdb.{tmdb_id}'
        elif search_term:
            params['SearchTerm'] = search_term
        else:
            return []

        endpoint = '/Items'
        response = self._make_request('GET', endpoint, params=params)

        return response.get('Items', []) if response else []

    def get_item_by_external_id(self, imdb_id: str = None, tmdb_id: str = None) -> Optional[Dict]:
        """
        Get a single item by external ID (IMDb or TMDb)

        Args:
            imdb_id: IMDb ID (e.g., tt1234567)
            tmdb_id: TMDb ID

        Returns:
            Item dictionary or None if not found
        """
        items = self.search_items(imdb_id=imdb_id, tmdb_id=tmdb_id)
        return items[0] if items else None

    def get_collections(self, name: str = None) -> List[Dict]:
        """
        Get existing collections

        Args:
            name: Optional name filter

        Returns:
            List of collections
        """
        params = {
            'Recursive': 'true',
            'IncludeItemTypes': 'BoxSet',
        }

        if name:
            params['SearchTerm'] = name

        endpoint = '/Items'
        response = self._make_request('GET', endpoint, params=params)

        collections = response.get('Items', []) if response else []

        # Filter by exact name if provided
        if name:
            collections = [c for c in collections if c.get('Name', '').lower() == name.lower()]

        return collections

    def create_collection(self, name: str, item_ids: List[str], parent_id: str = None,
                         is_locked: bool = False, overview: str = None,
                         display_order: str = None, sort_name: str = None) -> Optional[Dict]:
        """
        Create a new collection

        Args:
            name: Collection name
            item_ids: List of Emby item IDs to add to collection
            parent_id: Optional parent folder ID
            is_locked: Whether to lock the collection
            overview: Optional description/overview for the collection
            display_order: Optional display order ("PremiereDate" for release date, "SortName" for sort title)
            sort_name: Optional sort title for custom sorting of the collection itself

        Returns:
            Created collection data
        """
        params = {
            'Name': name,
            'Ids': ','.join(item_ids),
            'IsLocked': str(is_locked).lower()
        }

        if parent_id:
            params['ParentId'] = parent_id

        # Try to include overview in creation params (may not be supported by all Emby versions)
        if overview:
            params['Overview'] = overview

        endpoint = '/Collections'

        try:
            result = self._make_request('POST', endpoint, params=params)
            self.logger.info(f"Created collection '{name}' with {len(item_ids)} items")

            collection_id = result.get('Id') if result else None

            if collection_id:
                # Update display order if specified
                if display_order:
                    self.update_collection_display_order(collection_id, display_order)

                # Update overview and sort name if provided
                if overview or sort_name:
                    self.update_collection_metadata(collection_id, overview=overview, sort_name=sort_name)

            return result
        except Exception as e:
            self.logger.error(f"Failed to create collection '{name}': {e}")
            raise

    def add_to_collection(self, collection_id: str, item_ids: List[str]) -> bool:
        """
        Add items to an existing collection (batched to avoid URL length limits)

        Args:
            collection_id: Collection ID
            item_ids: List of item IDs to add

        Returns:
            True if successful
        """
        if not item_ids:
            return True

        # Batch items to avoid URL length limits (50 items per batch)
        batch_size = 50
        total_added = 0

        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i:i + batch_size]
            params = {'Ids': ','.join(batch)}
            endpoint = f'/Collections/{collection_id}/Items'

            try:
                self._make_request('POST', endpoint, params=params)
                total_added += len(batch)
                self.logger.info(f"Added batch of {len(batch)} items ({total_added}/{len(item_ids)})")
            except Exception as e:
                self.logger.error(f"Failed to add batch to collection: {e}")
                return False

        self.logger.info(f"Added {total_added} items to collection {collection_id}")
        return True

    def remove_from_collection(self, collection_id: str, item_ids: List[str]) -> bool:
        """
        Remove items from a collection (batched to avoid URL length limits)

        Args:
            collection_id: Collection ID
            item_ids: List of item IDs to remove

        Returns:
            True if successful
        """
        if not item_ids:
            return True

        # Batch items to avoid URL length limits (50 items per batch)
        batch_size = 50
        total_removed = 0

        for i in range(0, len(item_ids), batch_size):
            batch = item_ids[i:i + batch_size]
            params = {'Ids': ','.join(batch)}
            endpoint = f'/Collections/{collection_id}/Items'

            try:
                self._make_request('DELETE', endpoint, params=params)
                total_removed += len(batch)
                self.logger.info(f"Removed batch of {len(batch)} items ({total_removed}/{len(item_ids)})")
            except Exception as e:
                self.logger.error(f"Failed to remove batch from collection: {e}")
                return False

        self.logger.info(f"Removed {total_removed} items from collection {collection_id}")
        return True

    def get_collection_items(self, collection_id: str) -> List[Dict]:
        """
        Get all items in a collection

        Args:
            collection_id: Collection ID

        Returns:
            List of items in the collection
        """
        params = {
            'ParentId': collection_id,
            'Recursive': 'true'
        }

        endpoint = '/Items'
        response = self._make_request('GET', endpoint, params=params)

        return response.get('Items', []) if response else []

    def delete_collection(self, collection_id: str) -> bool:
        """
        Delete a collection (does NOT delete the movies/shows themselves)

        Args:
            collection_id: Collection ID to delete

        Returns:
            True if successful
        """
        endpoint = f'/Items/{collection_id}'

        try:
            self._make_request('DELETE', endpoint)
            self.logger.info(f"Deleted collection {collection_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete collection {collection_id}: {e}")
            return False

    def update_collection_display_order(self, collection_id: str, display_order: str) -> bool:
        """
        Update collection display order (how items are sorted within the collection)

        Args:
            collection_id: Collection ID
            display_order: Display order - "PremiereDate" (release date) or "SortName" (sort title)

        Returns:
            True if successful
        """
        if display_order not in ['PremiereDate', 'SortName']:
            self.logger.warning(f"Invalid display order '{display_order}'. Must be 'PremiereDate' or 'SortName'")
            return False

        try:
            # Emby requires fetching the full item, modifying it, and posting back
            # Get current item data (requires user context)
            if self.user_id:
                get_endpoint = f'/Users/{self.user_id}/Items/{collection_id}'
            else:
                # Try to get first user's ID
                users = self._make_request('GET', '/Users')
                if not users:
                    self.logger.warning("No user_id configured and no users found")
                    return False
                user_id = users[0].get('Id')
                get_endpoint = f'/Users/{user_id}/Items/{collection_id}'

            # Get the full item
            item = self._make_request('GET', get_endpoint)
            if not item:
                self.logger.error(f"Could not fetch collection {collection_id}")
                return False

            # Modify the DisplayOrder field
            item['DisplayOrder'] = display_order

            # Update via the Items endpoint
            update_endpoint = f'/Items/{collection_id}'
            self._make_request('POST', update_endpoint, json=item)

            self.logger.info(f"Set display order to '{display_order}' for collection {collection_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update display order for collection {collection_id}: {e}")
            return False

    def _REMOVED_set_user_display_preferences(self, collection_id: str, sort_by: str = "PremiereDate",
                                     sort_order: str = "Descending", user_filter: str = None,
                                     db_path: str = None) -> int:
        """
        Set display preferences for all users (or specific user) for a specific collection
        This controls how users see the collection sorted in the UI

        This method directly modifies the Emby SQLite database since the API is broken.

        Args:
            collection_id: Collection ID
            sort_by: Field to sort by (e.g., "PremiereDate", "SortName", "CommunityRating")
            sort_order: "Ascending" or "Descending"
            user_filter: Optional username to filter (only set preferences for this user)
            db_path: Optional path to users.db (auto-detected if not provided)

        Returns:
            Number of users successfully updated
        """
        import sqlite3
        import json
        import os
        from pathlib import Path

        self.logger.info(f"Setting user display preferences via database: {sort_by} {sort_order}")

        # Auto-detect database path if not provided
        if not db_path:
            possible_paths = [
                os.path.expanduser("~/.config/emby-server/data/users.db"),
                os.path.expanduser("~/Library/Application Support/Emby-Server/data/users.db"),
                "/var/lib/emby/data/users.db",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    db_path = path
                    break

        if not db_path or not os.path.exists(db_path):
            self.logger.error(f"Could not find Emby users.db file. Checked: {possible_paths}")
            return 0

        try:
            # Get all users from API
            users_response = self._make_request('GET', '/Users')
            if not users_response:
                self.logger.warning("No users found")
                return 0

            # Filter by username if specified
            if user_filter:
                users_response = [u for u in users_response if u.get('Name', '').lower() == user_filter.lower()]
                if not users_response:
                    self.logger.warning(f"User '{user_filter}' not found")
                    return 0
                self.logger.info(f"Filtering to user: {user_filter}")

            # Connect to database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get user ID mapping from database (guid to internal ID)
            # Note: Database stores GUIDs in Microsoft little-endian byte order
            cursor.execute("SELECT Id, hex(guid) FROM LocalUsersv2")
            db_users = cursor.fetchall()

            # Convert database GUIDs to standard format for matching
            guid_to_db_id = {}
            for db_id, db_guid_hex in db_users:
                # Database stores GUID in little-endian format, convert to standard UUID format
                # Format: DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD -> standard
                db_hex = db_guid_hex.lower()
                # Swap byte order for first 3 sections (Microsoft GUID format)
                standard_guid = (
                    db_hex[6:8] + db_hex[4:6] + db_hex[2:4] + db_hex[0:2] +  # First 4 bytes reversed
                    db_hex[10:12] + db_hex[8:10] +  # Next 2 bytes reversed
                    db_hex[14:16] + db_hex[12:14] +  # Next 2 bytes reversed
                    db_hex[16:32]  # Last 8 bytes unchanged
                )
                guid_to_db_id[standard_guid] = db_id

            self.logger.debug(f"Found {len(db_users)} users in database")

            success_count = 0
            # Set preferences for all common Emby client types to ensure it works everywhere
            # This covers web, TV apps, mobile apps, media players, etc.
            clients = [
                "web",           # Web browser
                "ATV",           # Android TV / Apple TV
                "AndroidTV",     # Android TV (alternate)
                "emby-mobile",   # Mobile apps
                "Roku",          # Roku devices
                "FireTV",        # Amazon Fire TV
                "Kodi",          # Kodi/Emby for Kodi
                "iOS",           # iOS devices
                "Android",       # Android phones/tablets
                "tvOS",          # Apple TV (tvOS)
                "Emby Theater",  # Emby Theater desktop app
                "Dashboard",     # Emby dashboard
            ]

            for user in users_response:
                user_guid = user.get('Id', '').replace('-', '').lower()
                user_name = user.get('Name', 'Unknown')

                self.logger.debug(f"Processing user '{user_name}' (GUID: {user_guid})")

                if user_guid not in guid_to_db_id:
                    self.logger.warning(f"User '{user_name}' GUID not found in database mapping")
                    self.logger.debug(f"  API GUID: {user_guid}")
                    self.logger.debug(f"  DB GUIDs: {list(guid_to_db_id.keys())[:3]}...")
                    continue

                db_user_id = guid_to_db_id[user_guid]
                self.logger.debug(f"  Mapped to DB user ID: {db_user_id}")

                # Set preferences for each client type
                user_success = False
                for client in clients:
                    try:
                        # Create the preference JSON matching Emby's exact format
                        # Note: Emby uses "d" for Descending and "a" for Ascending in CustomPrefs
                        sort_order_short = "d" if sort_order == "Descending" else "a"
                        pref_data = {
                            "Id": collection_id,
                            "SortBy": sort_by,
                            "SortOrder": sort_order,
                            "CustomPrefs": {
                                "FavoriteOnly": "false",
                                "ShowLabels": "true",
                                "SortBy": sort_by,
                                "UnwatchedOnly": "false",
                                "SortOrder": sort_order_short,
                                "GroupCollections": "false",
                                "PosterSize": "0",
                                "ImageType": "0"
                            },
                            "Client": client
                        }

                        # Create/get the key
                        key_name = f"displaypreferences_{client}_{collection_id}"
                        cursor.execute("INSERT OR IGNORE INTO UserSettingsKeys (Name) VALUES (?)", (key_name,))
                        cursor.execute("SELECT UserSettingsKeyId FROM UserSettingsKeys WHERE Name = ?", (key_name,))
                        key_result = cursor.fetchone()
                        if not key_result:
                            self.logger.debug(f"Failed to create/get key for user '{user_name}' client '{client}'")
                            continue
                        key_id = key_result[0]

                        # Insert or replace the preference
                        cursor.execute("INSERT OR REPLACE INTO UserSettings (UserId, UserSettingsKeyId, Value) VALUES (?, ?, ?)",
                                       (db_user_id, key_id, json.dumps(pref_data)))

                        user_success = True
                        self.logger.debug(f"Set {client} preferences for user '{user_name}': {sort_by} {sort_order}")

                    except Exception as e:
                        self.logger.debug(f"Failed to set {client} preferences for user '{user_name}': {e}")
                        continue

                if user_success:
                    success_count += 1

            conn.commit()
            conn.close()

            if success_count > 0:
                self.logger.info(f"✓ Set display preferences for {success_count}/{len(users_response)} users: {sort_by} {sort_order}")
                self.logger.info(f"  Applied to {len(clients)} client types (web, Android TV, Roku, iOS, etc.)")
                self.logger.info(f"  Users may need to refresh/restart their apps to see changes")
            else:
                self.logger.warning(f"Could not set display preferences for any users")

            return success_count

        except Exception as e:
            self.logger.error(f"Failed to set user display preferences via database: {e}")
            return 0

        # Keep the code commented for reference if Emby fixes the API in the future
        """
        try:
            # Get all users
            users_response = self._make_request('GET', '/Users')
            if not users_response:
                self.logger.warning("No users found")
                return 0

            # Filter by username if specified
            if user_filter:
                users_response = [u for u in users_response if u.get('Name', '').lower() == user_filter.lower()]
                if not users_response:
                    self.logger.warning(f"User '{user_filter}' not found")
                    return 0
                self.logger.info(f"Filtering to user: {user_filter}")

            success_count = 0
            for user in users_response:
                user_id = user.get('Id')
                user_name = user.get('Name', 'Unknown')

                try:
                    # Set display preferences for this user
                    endpoint = f'/DisplayPreferences/{collection_id}'
                    params = {
                        'userId': user_id,
                        'client': 'web'
                    }
                    data = {
                        'Id': collection_id,
                        'SortBy': sort_by,
                        'SortOrder': sort_order,
                        'Client': 'web',
                        'CustomPrefs': {}
                    }

                    self._make_request('POST', endpoint, params=params, json=data)
                    success_count += 1
                    self.logger.debug(f"Set display preferences for user '{user_name}': {sort_by} {sort_order}")

                except Exception as e:
                    self.logger.debug(f"Skipping user '{user_name}': {e}")
                    continue

            if success_count > 0:
                self.logger.info(f"Set display preferences for {success_count}/{len(users_response)} users: {sort_by} {sort_order}")
            else:
                self.logger.warning(f"Could not set display preferences for any users (API may not support this)")

            return success_count

        except Exception as e:
            self.logger.error(f"Failed to set user display preferences: {e}")
            return 0
        """

    def update_collection_metadata(self, collection_id: str, overview: str = None,
                                   sort_name: str = None, name: str = None) -> bool:
        """
        Update collection metadata (overview/description, sort title, name)

        Args:
            collection_id: Collection ID
            overview: Overview/description text
            sort_name: Sort title for custom collection ordering
            name: Display name (title) of the collection

        Returns:
            True if successful
        """
        if not overview and not sort_name and not name:
            return True

        try:
            # Get user ID for fetching the item
            if self.user_id:
                user_id = self.user_id
            else:
                # Get first user's ID
                users = self._make_request('GET', '/emby/Users')
                if not users:
                    self.logger.warning("No users found, cannot update collection metadata")
                    return False
                user_id = users[0].get('Id')

            # Get the current item data via user endpoint
            get_endpoint = f'/emby/Users/{user_id}/Items/{collection_id}'
            item = self._make_request('GET', get_endpoint)

            if not item:
                self.logger.error(f"Could not fetch collection {collection_id}")
                return False

            # Update the fields
            # Use metadata tracker to detect manual edits
            modified = False

            if overview:
                current_overview = item.get('Overview', '')
                tracked_overview = self.metadata_tracker.get_tracked_value(collection_id, 'Overview')

                # If we have a tracked value and current differs from it, it was manually edited
                if tracked_overview is not None and current_overview != tracked_overview:
                    self.logger.info(f"Preserving manual overview edit for collection {collection_id}")
                    # DO NOT update and DO NOT track new value - keep the manual edit
                else:
                    # Update if different from what we want to set
                    if current_overview != overview:
                        item['Overview'] = overview
                        modified = True
                    # Track what we're setting
                    self.metadata_tracker.track_metadata(collection_id, 'Overview', overview)

            if sort_name:
                current_sort_name = item.get('SortName', '')
                tracked_sort_name = self.metadata_tracker.get_tracked_value(collection_id, 'SortName')

                # If we have a tracked value and current differs from it, it was manually edited
                if tracked_sort_name is not None and current_sort_name != tracked_sort_name:
                    self.logger.info(f"Preserving manual sort name edit for collection {collection_id}")
                    # DO NOT update and DO NOT track new value - keep the manual edit
                else:
                    # Update if different from what we want to set
                    if current_sort_name != sort_name:
                        item['SortName'] = sort_name
                        item['ForcedSortName'] = sort_name  # Also set ForcedSortName
                        modified = True
                    # Track what we're setting
                    self.metadata_tracker.track_metadata(collection_id, 'SortName', sort_name)

            if name:
                current_name = item.get('Name', '')
                tracked_name = self.metadata_tracker.get_tracked_value(collection_id, 'Name')

                # If we have a tracked value and current differs from it, it was manually edited
                if tracked_name is not None and current_name != tracked_name:
                    self.logger.info(f"Preserving manual name edit for collection {collection_id}")
                    # DO NOT update and DO NOT track new value - keep the manual edit
                else:
                    # Update if different from what we want to set
                    if current_name != name:
                        item['Name'] = name
                        modified = True
                    # Track what we're setting
                    self.metadata_tracker.track_metadata(collection_id, 'Name', name)

            if not modified:
                return True

            # Update via the Items endpoint (POST to update)
            update_endpoint = f'/emby/Items/{collection_id}'
            self._make_request('POST', update_endpoint, json=item)

            collection_name = item.get('Name', collection_id)
            changes = []
            if name:
                changes.append(f"name to '{name}'")
            if overview:
                changes.append(f"overview")
            if sort_name:
                changes.append(f"sort title to '{sort_name}'")

            self.logger.info(f"Updated {collection_name}: {', '.join(changes)}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to update collection metadata for {collection_id}: {e}")
            return False

    def set_collection_image(self, collection_id: str, image_path: str) -> bool:
        """
        Set/upload a primary image for a collection

        Args:
            collection_id: Collection ID
            image_path: Path to the image file (relative or absolute)

        Returns:
            True if successful
        """
        import os
        import base64

        if not os.path.exists(image_path):
            self.logger.error(f"Image file not found: {image_path}")
            return False

        try:
            # Determine image content type
            ext = os.path.splitext(image_path)[1].lower()
            content_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }
            content_type = content_types.get(ext, 'image/jpeg')

            # Read and base64 encode the image file
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Encode to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            # Upload to Emby
            # Note: Image upload requires /emby prefix, base64 encoding, and proper MIME type
            endpoint = f'/emby/Items/{collection_id}/Images/Primary/0'
            url = f"{self.base_url}{endpoint}?api_key={self.api_key}"

            # Post the base64-encoded image data with proper content type
            # Emby uses the Content-Type header to determine the image format
            headers = {
                'Content-Type': content_type
            }

            response = requests.post(url, data=image_base64, headers=headers)
            response.raise_for_status()

            self.logger.info(f"Successfully set image for collection {collection_id} from {image_path}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to set image for collection {collection_id}: {e}")
            return False

    def collection_has_custom_image(self, collection_id: str) -> bool:
        """
        Check if a collection has a custom primary image set

        Args:
            collection_id: Collection ID

        Returns:
            True if collection has a custom image
        """
        try:
            # Get user ID
            if self.user_id:
                user_id = self.user_id
            else:
                users = self._make_request('GET', '/emby/Users')
                if not users:
                    return False
                user_id = users[0].get('Id')

            # Get collection info
            endpoint = f'/emby/Users/{user_id}/Items/{collection_id}'
            item = self._make_request('GET', endpoint)

            if not item:
                return False

            # Check if it has ImageTags for Primary image
            image_tags = item.get('ImageTags', {})
            return 'Primary' in image_tags

        except Exception as e:
            self.logger.error(f"Error checking image for collection {collection_id}: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test connection to Emby server

        Returns:
            True if connection successful
        """
        try:
            endpoint = '/System/Info'
            info = self._make_request('GET', endpoint)
            self.logger.info(f"Connected to Emby server: {info.get('ServerName', 'Unknown')} v{info.get('Version', 'Unknown')}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Emby server: {e}")
            return False
