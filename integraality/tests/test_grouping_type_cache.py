"""Tests for GroupingTypeCache."""

import unittest
from unittest.mock import MagicMock

import fakeredis

from ..grouping_type_cache import REDIS_HASH_KEY, GroupingTypeCache


class TestGroupingTypeCache(unittest.TestCase):
    def _redis(self):
        return fakeredis.FakeStrictRedis(decode_responses=True)

    def test_preloads_existing_hash(self):
        redis = self._redis()
        redis.hset(REDIS_HASH_KEY, "wdt:P571", "year")
        redis.hset(REDIS_HASH_KEY, "^schema:about", "sitelink")
        cache = GroupingTypeCache(redis)
        self.assertEqual(cache.get("wdt:P571"), "year")
        self.assertEqual(cache.get("^schema:about"), "sitelink")
        self.assertIsNone(cache.get("wdt:P21"))

    def test_set_writes_through_to_dict_and_redis(self):
        redis = self._redis()
        cache = GroupingTypeCache(redis)
        cache.set("wdt:P21", "item")
        # In-process immediately...
        self.assertEqual(cache.get("wdt:P21"), "item")
        # ...and persisted, so a fresh cache preloads it.
        self.assertEqual(GroupingTypeCache(redis).get("wdt:P21"), "item")

    def test_none_token_is_not_cached(self):
        # A failed resolution (None) must stay retryable -- never persisted.
        redis = self._redis()
        cache = GroupingTypeCache(redis)
        cache.set("wdt:P999", None)
        self.assertIsNone(cache.get("wdt:P999"))
        self.assertEqual(redis.hgetall(REDIS_HASH_KEY), {})

    def test_degrades_without_redis(self):
        cache = GroupingTypeCache()  # no client
        self.assertIsNone(cache.get("wdt:P571"))
        cache.set("wdt:P571", "year")
        self.assertEqual(cache.get("wdt:P571"), "year")  # in-process still works

    def test_preload_failure_degrades_to_empty(self):
        client = MagicMock()
        client.hgetall.side_effect = Exception("redis down")
        cache = GroupingTypeCache(client)  # must not raise
        self.assertIsNone(cache.get("wdt:P571"))

    def test_write_failure_is_swallowed(self):
        client = MagicMock()
        client.hgetall.return_value = {}
        client.hset.side_effect = Exception("redis down")
        cache = GroupingTypeCache(client)
        cache.set("wdt:P21", "item")  # must not raise
        # Still cached in-process despite the Redis write failing.
        self.assertEqual(cache.get("wdt:P21"), "item")

    def test_decodes_bytes_values(self):
        # A client without decode_responses returns bytes; preload must str them.
        client = MagicMock()
        client.hgetall.return_value = {b"wdt:P571": b"year"}
        cache = GroupingTypeCache(client)
        self.assertEqual(cache.get("wdt:P571"), "year")
