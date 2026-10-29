"""Redis cache for parsed configs."""

# Inspired/copied from https://github.com/taylorhakes/python-redis-cache/blob/master/redis_cache/__init__.py, MIT-licensed

import os
import pickle

DEFAULT_TTL = 604800  # 1 week

# Toolforge Redis; overridable via REDIS_HOST (set to "redis" in Docker).
DEFAULT_REDIS_HOST = "tools-redis.svc.eqiad.wmflabs"


def redis_host():
    """The Redis host from REDIS_HOST, defaulting to Toolforge's."""
    return os.getenv("REDIS_HOST", DEFAULT_REDIS_HOST)


class RedisCache:
    def __init__(self, cache_client, prefix="integraality"):
        self.prefix = prefix
        self.client = cache_client

    def make_key(self, key):
        return f"{self.prefix}:{key}"

    def get_cache_value(self, key):
        ns_key = self.make_key(key)
        cached_value = self.client.get(ns_key)
        if cached_value:
            try:
                return pickle.loads(cached_value)
            except (AttributeError, ModuleNotFoundError, pickle.UnpicklingError):
                self.client.delete(ns_key)
                return None
        else:
            return None

    def set_cache_value(self, key, value):
        ns_key = self.make_key(key)
        cached_value = pickle.dumps(value)
        pipe = self.client.pipeline()
        pipe.set(ns_key, cached_value)
        pipe.expire(ns_key, DEFAULT_TTL)
        pipe.execute()

    def invalidate(self, key):
        ns_key = self.make_key(key)
        pipe = self.client.pipeline()
        pipe.delete(ns_key)
        pipe.execute()

    def list_keys(self):
        return self.client.keys()

    def flushall(self):
        self.client.flushall()
