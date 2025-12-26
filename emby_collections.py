#!/usr/bin/env python3
"""
Emby Collection Manager
Main script to sync Emby collections with external movie lists from MDBList and Trakt
"""

import sys
import os
import logging
import yaml
import argparse
import schedule
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from emby_client import EmbyClient
from mdblist_fetcher import MDBListFetcher
from trakt_fetcher import TraktFetcher
from collection_manager import CollectionManager


class EmbyCollectionSync:
    """Main application class for syncing Emby collections"""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize the sync application

        Args:
            config_path: Path to config file
        """
        self.config_path = config_path
        self.config = None
        self.logger = None
        self.emby_client = None
        self.mdblist_fetcher = None
        self.trakt_fetcher = None
        self.collection_manager = None

    def load_config(self):
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            print(f"ERROR: Config file not found: {self.config_path}")
            print("Please copy config.yaml.example to config.yaml and configure it")
            sys.exit(1)

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Validate required config
        if not self.config.get('emby', {}).get('url'):
            print("ERROR: emby.url is required in config")
            sys.exit(1)

        if not self.config.get('emby', {}).get('api_key'):
            print("ERROR: emby.api_key is required in config")
            sys.exit(1)

    def setup_logging(self):
        """Setup logging configuration"""
        settings = self.config.get('settings', {})
        log_level = settings.get('log_level', 'INFO')
        log_file = settings.get('log_file', 'emby_collections.log')

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Setup root logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, log_level))

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        self.logger = logger

    def initialize_clients(self):
        """Initialize API clients"""
        # Emby client
        emby_config = self.config['emby']
        self.emby_client = EmbyClient(
            base_url=emby_config['url'],
            api_key=emby_config['api_key'],
            user_id=emby_config.get('user_id')
        )

        # Test Emby connection
        if not self.emby_client.test_connection():
            self.logger.error("Failed to connect to Emby server. Check your configuration.")
            sys.exit(1)

        # MDBList fetcher
        mdblist_config = self.config.get('mdblist', {})
        if mdblist_config.get('api_key'):
            self.mdblist_fetcher = MDBListFetcher(mdblist_config['api_key'])
            self.mdblist_fetcher.test_connection()
        else:
            self.logger.warning("MDBList API key not configured")

        # Trakt fetcher
        trakt_config = self.config.get('trakt', {})
        if trakt_config.get('client_id'):
            self.trakt_fetcher = TraktFetcher(
                client_id=trakt_config['client_id'],
                client_secret=trakt_config.get('client_secret'),
                access_token=trakt_config.get('access_token')
            )
            self.trakt_fetcher.test_connection()
        else:
            self.logger.warning("Trakt API key not configured")

        # Collection manager
        settings = self.config.get('settings', {})
        self.collection_manager = CollectionManager(
            emby_client=self.emby_client,
            match_priority=settings.get('match_priority', ['imdb_id', 'tmdb_id', 'title']),
            remove_missing=settings.get('remove_missing', True),
            dry_run=settings.get('dry_run', False),
            clear_collections=settings.get('clear_collections', False),
            delete_unlisted=settings.get('delete_unlisted', False)
        )

    def is_collection_in_season(self, collection_config: Dict) -> bool:
        """
        Check if a collection is currently in season based on seasonal config

        Args:
            collection_config: Collection configuration dict

        Returns:
            True if collection should be active, False otherwise
        """
        seasonal = collection_config.get('seasonal')
        if not seasonal:
            return True  # No seasonal config = always active

        now = datetime.now()
        current_month = now.month
        current_day = now.day

        start_month = seasonal.get('start_month')
        start_day = seasonal.get('start_day')
        end_month = seasonal.get('end_month')
        end_day = seasonal.get('end_day')

        if not all([start_month, start_day, end_month, end_day]):
            self.logger.warning(f"Invalid seasonal config for {collection_config.get('name')}, treating as always active")
            return True

        # Convert to comparable format (month * 100 + day)
        current_date = current_month * 100 + current_day
        start_date = start_month * 100 + start_day
        end_date = end_month * 100 + end_day

        # Handle year wrap-around (e.g., Dec 15 to Jan 5)
        if start_date <= end_date:
            # Normal range within same year
            in_season = start_date <= current_date <= end_date
        else:
            # Range wraps around year boundary
            in_season = current_date >= start_date or current_date <= end_date

        return in_season

    def sync_all_collections(self):
        """Sync all configured collections"""
        collections = self.config.get('collections', [])

        if not collections:
            self.logger.warning("No collections configured")
            return

        self.logger.info(f"Starting sync of {len(collections)} collections")
        self.logger.info("=" * 60)

        total_stats = {
            'collections_processed': 0,
            'collections_failed': 0,
            'total_added': 0,
            'total_removed': 0,
            'total_not_found': 0
        }

        for collection_config in collections:
            try:
                collection_name = collection_config.get('name')

                # Check if collection is in season
                if not self.is_collection_in_season(collection_config):
                    self.logger.info(f"Collection '{collection_name}' is out of season, hiding it")
                    # Hide the collection by deleting it (only the collection, not the movies)
                    self.collection_manager.hide_collection(collection_name)
                    continue

                # Collection is in season, sync it
                stats = self.sync_collection(collection_config)
                total_stats['collections_processed'] += 1
                total_stats['total_added'] += stats['added']
                total_stats['total_removed'] += stats['removed']
                total_stats['total_not_found'] += stats['not_found']
            except Exception as e:
                self.logger.error(f"Failed to sync collection: {e}", exc_info=True)
                total_stats['collections_failed'] += 1

        # Delete unlisted collections if requested
        deleted_count = self.collection_manager.delete_unlisted_collections()
        if deleted_count > 0:
            total_stats['collections_deleted'] = deleted_count

        # Summary
        self.logger.info("=" * 60)
        self.logger.info("Sync Summary:")
        self.logger.info(f"  Collections processed: {total_stats['collections_processed']}")
        self.logger.info(f"  Collections failed: {total_stats['collections_failed']}")
        if 'collections_deleted' in total_stats:
            self.logger.info(f"  Collections deleted: {total_stats['collections_deleted']}")
        self.logger.info(f"  Total items added: {total_stats['total_added']}")
        self.logger.info(f"  Total items removed: {total_stats['total_removed']}")
        self.logger.info(f"  Total not found: {total_stats['total_not_found']}")
        self.logger.info("=" * 60)

    def sync_collection(self, collection_config: Dict) -> Dict:
        """
        Sync a single collection

        Args:
            collection_config: Collection configuration dict

        Returns:
            Stats dict
        """
        name = collection_config.get('name')
        source = collection_config.get('source')
        overview = collection_config.get('overview')
        image_path = collection_config.get('image')

        self.logger.info(f"Syncing collection: {name} (source: {source})")

        # Fetch movies from source
        movies = self.fetch_movies_from_source(collection_config)

        if not movies:
            self.logger.warning(f"No movies fetched for collection '{name}'")
            return {'added': 0, 'removed': 0, 'total': 0, 'not_found': 0}

        # Apply custom sorting if specified
        sort_by = collection_config.get('sort_by')
        if sort_by and movies:
            if sort_by == 'rating':
                movies = sorted(movies, key=lambda x: x.get('rating', 0), reverse=True)
                self.logger.info(f"Sorted {len(movies)} movies by rating (highest first)")
            elif sort_by == 'votes':
                movies = sorted(movies, key=lambda x: x.get('votes', 0), reverse=True)
                self.logger.info(f"Sorted {len(movies)} movies by votes (most first)")
            elif sort_by == 'title':
                movies = sorted(movies, key=lambda x: x.get('title', ''))
                self.logger.info(f"Sorted {len(movies)} movies by title (A-Z)")

        # Sync with Emby
        stats = self.collection_manager.sync_collection(name, movies, overview=overview, image_path=image_path)

        self.logger.info(f"Collection '{name}': {stats['added']} added, {stats['removed']} removed, "
                        f"{stats['not_found']} not found in library")

        return stats

    def fetch_movies_from_source(self, collection_config: Dict) -> List[Dict]:
        """
        Fetch movies from configured source

        Args:
            collection_config: Collection configuration

        Returns:
            List of movies
        """
        source = collection_config.get('source', '').lower()

        if source == 'mdblist':
            if not self.mdblist_fetcher:
                self.logger.error("MDBList fetcher not initialized (missing API key?)")
                return []

            list_id = collection_config.get('list_id')
            limit = collection_config.get('limit')

            return self.mdblist_fetcher.fetch_list(list_id, limit)

        elif source == 'trakt':
            if not self.trakt_fetcher:
                self.logger.error("Trakt fetcher not initialized (missing API key?)")
                return []

            # Check if it's a user list or a category
            username = collection_config.get('username')
            list_slug = collection_config.get('list_slug')

            if username and list_slug:
                # Fetch user list
                limit = collection_config.get('limit')
                return self.trakt_fetcher.fetch_user_list(username, list_slug, limit)
            else:
                # Fetch by category
                category = collection_config.get('category', 'trending')
                limit = collection_config.get('limit', 50)
                time_period = collection_config.get('time_period', 'weekly')
                return self.trakt_fetcher.fetch_movies(category, limit, time_period=time_period)

        else:
            self.logger.error(f"Unknown source: {source}")
            return []

    def run_once(self):
        """Run sync once"""
        self.logger.info("Starting Emby Collection Sync")
        self.sync_all_collections()
        self.logger.info("Sync completed")

    def run_scheduled(self):
        """Run with scheduler"""
        settings = self.config.get('settings', {})
        schedule_time = settings.get('schedule_time', '02:00')

        self.logger.info(f"Scheduling daily sync at {schedule_time}")
        schedule.every().day.at(schedule_time).do(self.run_once)

        # Run once immediately
        self.run_once()

        # Then run on schedule
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    def run(self, once: bool = False, config_loaded: bool = False):
        """
        Main run method

        Args:
            once: If True, run once and exit. Otherwise, run on schedule
            config_loaded: If True, config already loaded (for CLI overrides)
        """
        if not config_loaded:
            self.load_config()
        self.setup_logging()
        self.initialize_clients()

        if once:
            self.run_once()
        else:
            self.run_scheduled()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Sync Emby collections with external movie lists'
    )
    parser.add_argument(
        '-c', '--config',
        default='config.yaml',
        help='Path to config file (default: config.yaml)'
    )
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run once and exit (instead of scheduling)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry run mode (don\'t actually modify collections)'
    )
    parser.add_argument(
        '--clear',
        action='store_true',
        help='Clear existing collections before syncing (items only, NOT the movies/shows themselves)'
    )
    parser.add_argument(
        '--delete-unlisted',
        action='store_true',
        help='Delete collections not in config (WARNING: deletes collections, NOT movies/shows)'
    )

    args = parser.parse_args()

    # Create app
    app = EmbyCollectionSync(config_path=args.config)

    # Load config first to allow command-line overrides
    app.load_config()

    # Override settings from command line
    if args.dry_run:
        if 'settings' not in app.config:
            app.config['settings'] = {}
        app.config['settings']['dry_run'] = True

    if args.clear:
        if 'settings' not in app.config:
            app.config['settings'] = {}
        app.config['settings']['clear_collections'] = True

    if args.delete_unlisted:
        if 'settings' not in app.config:
            app.config['settings'] = {}
        app.config['settings']['delete_unlisted'] = True

    try:
        app.run(once=args.once, config_loaded=True)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
