"""
Trakt.tv API Fetcher
Fetches movie lists from Trakt.tv
"""

import requests
import logging
from typing import List, Dict, Optional


class TraktFetcher:
    """Fetcher for Trakt.tv API"""

    BASE_URL = "https://api.trakt.tv"
    API_VERSION = "2"

    # Available categories for movies
    VALID_CATEGORIES = [
        'trending',
        'popular',
        'watched',
        'played',
        'anticipated',
        'boxoffice',
        'updates'
    ]

    def __init__(self, client_id: str, client_secret: str = None, access_token: str = None):
        """
        Initialize Trakt fetcher

        Args:
            client_id: Trakt API client ID
            client_secret: Optional client secret for OAuth
            access_token: Optional access token for authenticated requests
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.logger = logging.getLogger(__name__)

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'trakt-api-version': self.API_VERSION,
            'trakt-api-key': client_id
        })

        if access_token:
            self.session.headers['Authorization'] = f'Bearer {access_token}'

    def fetch_movies(self, category: str = 'trending', limit: int = 50,
                     extended: str = 'full', time_period: str = 'weekly') -> List[Dict]:
        """
        Fetch movies from Trakt by category

        Args:
            category: Category (trending, popular, watched, played, anticipated, boxoffice)
            limit: Number of movies to fetch (max varies by endpoint)
            extended: Extended info level ('min', 'full', 'metadata')
            time_period: Time period for watched/played (weekly, monthly, yearly, all)

        Returns:
            List of movies with metadata
        """
        if category not in self.VALID_CATEGORIES:
            self.logger.error(f"Invalid category: {category}. Valid: {self.VALID_CATEGORIES}")
            return []

        # Add time period for watched/played categories
        if category in ['watched', 'played']:
            endpoint = f"/movies/{category}/{time_period}"
        else:
            endpoint = f"/movies/{category}"

        params = {
            'limit': min(limit, 100),  # Trakt typically limits to 100
            'extended': extended
        }

        try:
            # Paginate to get more results if limit > 100
            normalized_movies = []
            page = 1
            per_page = min(100, limit)  # Max 100 per page

            while len(normalized_movies) < limit:
                params['page'] = page
                params['limit'] = per_page

                url = f"{self.BASE_URL}{endpoint}"
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                movies_data = response.json()

                # If no more results, break
                if not movies_data:
                    break

                # Normalize the data
                for item in movies_data:
                    # Trakt returns either just movie object or {movie: ..., watchers: ...} etc
                    movie = item.get('movie', item) if isinstance(item, dict) else item

                    normalized = self._normalize_movie_data(movie)
                    if normalized:
                        normalized_movies.append(normalized)

                        # Stop if we've reached the requested limit
                        if len(normalized_movies) >= limit:
                            break

                # If we got fewer than per_page results, we've reached the end
                if len(movies_data) < per_page:
                    break

                page += 1

            self.logger.info(f"Fetched {len(normalized_movies)} movies from Trakt ({category})")
            return normalized_movies

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch Trakt movies ({category}): {e}")
            return []

    def fetch_user_list(self, username: str, list_slug: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Fetch a user's custom list

        Args:
            username: Trakt username
            list_slug: List slug/ID
            limit: Optional limit on items

        Returns:
            List of movies
        """
        endpoint = f"/users/{username}/lists/{list_slug}/items/movies"
        params = {'extended': 'full'}

        if limit:
            params['limit'] = limit

        try:
            url = f"{self.BASE_URL}{endpoint}"
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            items_data = response.json()

            normalized_movies = []
            for item in items_data:
                movie = item.get('movie', item)
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    # Add list-specific metadata (rank from list)
                    if 'rank' in item:
                        normalized['list_rank'] = item['rank']
                    normalized_movies.append(normalized)

            self.logger.info(f"Fetched {len(normalized_movies)} movies from Trakt list: {username}/{list_slug}")
            return normalized_movies

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch Trakt user list {username}/{list_slug}: {e}")
            return []

    def _normalize_movie_data(self, movie: Dict) -> Optional[Dict]:
        """
        Normalize movie data to consistent format

        Args:
            movie: Raw movie data from Trakt

        Returns:
            Normalized movie dict
        """
        try:
            ids = movie.get('ids', {})

            normalized = {
                'title': movie.get('title', 'Unknown'),
                'year': movie.get('year'),
                'imdb_id': ids.get('imdb'),
                'tmdb_id': str(ids.get('tmdb')) if ids.get('tmdb') else None,
                'trakt_id': str(ids.get('trakt')) if ids.get('trakt') else None,
                'slug': ids.get('slug'),
                'rating': movie.get('rating'),  # Trakt rating (0-10)
                'votes': movie.get('votes'),    # Number of votes
                'type': 'movie',
                'source': 'trakt'
            }

            # Only return if we have at least one ID
            if normalized['imdb_id'] or normalized['tmdb_id']:
                return normalized
            else:
                self.logger.warning(f"Movie missing IDs: {normalized['title']} ({normalized['year']})")
                return None

        except Exception as e:
            self.logger.error(f"Error normalizing Trakt movie data: {e}")
            return None

    def search_movie(self, query: str, year: Optional[int] = None) -> List[Dict]:
        """
        Search for movies by title

        Args:
            query: Search query
            year: Optional year filter

        Returns:
            List of matching movies
        """
        endpoint = "/search/movie"
        params = {
            'query': query,
            'extended': 'full'
        }

        if year:
            params['years'] = year

        try:
            url = f"{self.BASE_URL}{endpoint}"
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            results = response.json()

            normalized_movies = []
            for result in results:
                movie = result.get('movie', {})
                normalized = self._normalize_movie_data(movie)
                if normalized:
                    normalized_movies.append(normalized)

            return normalized_movies

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to search Trakt for '{query}': {e}")
            return []

    def test_connection(self) -> bool:
        """
        Test API connection

        Returns:
            True if connection successful
        """
        try:
            # Try to fetch trending movies (should work without auth)
            endpoint = f"{self.BASE_URL}/movies/trending"
            params = {'limit': 1}

            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()

            self.logger.info("Successfully connected to Trakt API")
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to connect to Trakt API: {e}")
            return False
