"""
MDBList API Fetcher
Fetches movie lists from MDBList.com
"""

import requests
import logging
from typing import List, Dict, Optional


class MDBListFetcher:
    """Fetcher for MDBList.com API"""

    BASE_URL = "https://api.mdblist.com"
    LIST_URL_TEMPLATE = "https://mdblist.com/lists/{list_id}/json"

    def __init__(self, api_key: str):
        """
        Initialize MDBList fetcher

        Args:
            api_key: MDBList API key
        """
        self.api_key = api_key
        self.logger = logging.getLogger(__name__)

        self.session = requests.Session()
        self.session.params = {'apikey': api_key}

    def fetch_list(self, list_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch a list from MDBList

        Args:
            list_id: List identifier (e.g., "username/list-name" or "top-rated-movies")
            limit: Optional limit on number of items to return

        Returns:
            List of movies with metadata
        """
        # Try the JSON endpoint first (simpler, no API key needed for public lists)
        url = self.LIST_URL_TEMPLATE.format(list_id=list_id)

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            movies = response.json()

            if not isinstance(movies, list):
                self.logger.error(f"Unexpected response format from MDBList: {type(movies)}")
                return []

            # Normalize the data structure
            normalized_movies = []
            for movie in movies:
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    normalized_movies.append(normalized)

            # Apply limit if specified
            if limit and limit > 0:
                normalized_movies = normalized_movies[:limit]

            self.logger.info(f"Fetched {len(normalized_movies)} movies from MDBList list: {list_id}")
            return normalized_movies

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch MDBList list '{list_id}': {e}")
            # Try API endpoint as fallback
            return self._fetch_via_api(list_id, limit)

    def _fetch_via_api(self, list_id: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch list via API endpoint (fallback method)

        Args:
            list_id: List identifier
            limit: Optional limit on number of items

        Returns:
            List of movies
        """
        # API endpoint for lists
        url = f"{self.BASE_URL}/lists/{list_id}/items"

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            movies = data if isinstance(data, list) else data.get('items', [])

            normalized_movies = []
            for movie in movies:
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    normalized_movies.append(normalized)

            if limit and limit > 0:
                normalized_movies = normalized_movies[:limit]

            self.logger.info(f"Fetched {len(normalized_movies)} movies from MDBList API: {list_id}")
            return normalized_movies

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch MDBList via API '{list_id}': {e}")
            return []

    def _normalize_movie_data(self, movie: Dict) -> Optional[Dict]:
        """
        Normalize movie data to a consistent format

        Args:
            movie: Raw movie data from MDBList

        Returns:
            Normalized movie dict with standard fields
        """
        try:
            # MDBList can return different formats
            # Try to extract the common fields
            year = movie.get('year') or movie.get('release_year')
            if not year and movie.get('release_date'):
                year = str(movie.get('release_date'))[:4]

            normalized = {
                'title': movie.get('title') or movie.get('name', 'Unknown'),
                'year': year,
                'imdb_id': self._extract_imdb_id(movie),
                'tmdb_id': self._extract_tmdb_id(movie),
                'type': movie.get('type', 'movie'),
                'source': 'mdblist'
            }

            # Only return if we have at least one ID
            if normalized['imdb_id'] or normalized['tmdb_id']:
                return normalized
            else:
                self.logger.warning(f"Movie missing IDs: {normalized['title']} ({normalized['year']})")
                return None

        except Exception as e:
            self.logger.error(f"Error normalizing movie data: {e}")
            return None

    def _extract_imdb_id(self, movie: Dict) -> Optional[str]:
        """Extract IMDb ID from various possible fields"""
        # Direct field
        imdb_id = movie.get('imdb_id') or movie.get('imdbid')

        # From ID object
        if not imdb_id and 'id' in movie:
            if isinstance(movie['id'], dict):
                imdb_id = movie['id'].get('imdb')

        # Ensure proper format (tt + numbers)
        if imdb_id:
            imdb_id = str(imdb_id)
            if not imdb_id.startswith('tt'):
                imdb_id = f'tt{imdb_id}'

        return imdb_id

    def _extract_tmdb_id(self, movie: Dict) -> Optional[str]:
        """Extract TMDb ID from various possible fields"""
        # Direct field
        tmdb_id = movie.get('tmdb_id') or movie.get('tmdbid')

        # From ID object
        if not tmdb_id and 'id' in movie:
            if isinstance(movie['id'], dict):
                tmdb_id = movie['id'].get('tmdb')

        return str(tmdb_id) if tmdb_id else None

    def test_connection(self) -> bool:
        """
        Test API connection

        Returns:
            True if connection successful
        """
        try:
            # Try to fetch user info or a simple endpoint
            url = f"{self.BASE_URL}/"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            self.logger.info("Successfully connected to MDBList API")
            return True
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"MDBList API test failed (this might be OK): {e}")
            # MDBList might not have a root endpoint, so we'll just warn
            return True  # Don't fail completely
