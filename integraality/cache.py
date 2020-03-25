# Inspired/copied from https://github.com/taylorhakes/python-redis-cache/blob/master/redis_cache/__init__.py, MIT-licensed

import pickle

DEFAULT_TTL = 604800  # 1 week


class RedisCache:

    def __init__(self, cache_client, prefix="integraality"):
        self.prefix = prefix
        self.client = cache_client

    def make_key(self, key):
        return "{0}:{1}".format(self.prefix, key)

    def get_cache_value(self, key):
        ns_key = self.make_key(key)
        cached_value = self.client.get(ns_key)
        if cached_value:
            return pickle.loads(cached_value)
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
        print("Invalidating key %s" % ns_key)
        pipe = self.client.pipeline()
        pipe.delete(ns_key)
        pipe.execute()

    def list_keys(self):
        keys = self.client.keys()
        print("%s keys in Redis" % len(keys))

    def flushall(self):
        print("Deleting all keys")
        self.client.flushall()
