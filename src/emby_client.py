"""
Emby API Client
Handles all interactions with the Emby server API
"""

import requests
import logging
from typing import List, Dict, Optional, Any
from urllib.parse import urljoin, quote


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
                         is_locked: bool = False) -> Optional[Dict]:
        """
        Create a new collection

        Args:
            name: Collection name
            item_ids: List of Emby item IDs to add to collection
            parent_id: Optional parent folder ID
            is_locked: Whether to lock the collection

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

        endpoint = '/Collections'

        try:
            result = self._make_request('POST', endpoint, params=params)
            self.logger.info(f"Created collection '{name}' with {len(item_ids)} items")
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
