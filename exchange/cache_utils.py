from django.core.cache import cache
from django.conf import settings
import hashlib
import json


class TTLCacheManager:
    """TTL cache manager for consistent keying and timeouts."""

    @staticmethod
    def generate_cache_key(prefix, params):
        """Generate a stable cache key based on a prefix and params dict."""
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{param_hash}"

    @staticmethod
    def get_cached_data(cache_key, cache_timeout):
        """Fetch data from cache by key."""
        return cache.get(cache_key)

    @staticmethod
    def set_cached_data(cache_key, data, cache_timeout):
        """Store data into cache with timeout."""
        cache.set(cache_key, data, cache_timeout)

    @staticmethod
    def get_cache_timeout(cache_type):
        """Lookup timeout seconds from settings for a given cache type."""
        return settings.CACHE_TIMEOUT.get(cache_type, 300)

