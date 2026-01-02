"""
Metadata Tracker
Tracks collection metadata set by the script to detect manual user edits
"""

import json
import os
import logging
from typing import Dict, Optional


class MetadataTracker:
    """Tracks metadata values set by the script to detect manual edits in Emby"""

    def __init__(self, cache_file: str = None):
        """
        Initialize metadata tracker

        Args:
            cache_file: Path to cache file (default: .metadata_cache.json in current dir)
        """
        self.logger = logging.getLogger(__name__)
        self.cache_file = cache_file or os.path.join(os.getcwd(), '.metadata_cache.json')
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """Load cache from disk"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load metadata cache: {e}")
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save metadata cache: {e}")

    def track_metadata(self, collection_id: str, field: str, value: str):
        """
        Track a metadata value we set

        Args:
            collection_id: Collection ID
            field: Field name (e.g., 'Overview', 'Name', 'SortName')
            value: Value we set
        """
        if collection_id not in self.cache:
            self.cache[collection_id] = {}

        self.cache[collection_id][field] = value
        self._save_cache()

    def get_tracked_value(self, collection_id: str, field: str) -> Optional[str]:
        """
        Get the last value we set for a field

        Args:
            collection_id: Collection ID
            field: Field name

        Returns:
            Last value we set, or None if never set
        """
        return self.cache.get(collection_id, {}).get(field)

    def clear_collection(self, collection_id: str):
        """
        Clear tracking for a collection (e.g., when deleted)

        Args:
            collection_id: Collection ID to clear
        """
        if collection_id in self.cache:
            del self.cache[collection_id]
            self._save_cache()
