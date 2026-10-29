"""Cross-run cache of grouping-type resolutions (predicate -> token)."""

import logging

logger = logging.getLogger(__name__)

REDIS_HASH_KEY = "integraality:grouping_types"
TTL_SECONDS = 2592000  # 30 days


class GroupingTypeCache:
    def __init__(self, redis_client=None):
        self.client = redis_client
        self._local = self._preload()

    def _preload(self):
        """Bulk-load the persisted predicate->token map in one HGETALL."""
        if self.client is None:
            return {}
        try:
            raw = self.client.hgetall(REDIS_HASH_KEY)
        except Exception as e:
            logger.warning("GroupingTypeCache preload failed, running in-memory: %s", e)
            return {}
        return {_text(k): _text(v) for k, v in raw.items()}

    def get(self, predicate):
        """The cached grouping-type token for a predicate, or None."""
        return self._local.get(predicate)

    def set(self, predicate, token):
        """Cache a successful resolution (None is never cached -- stays retryable)."""
        if token is None:
            return
        self._local[predicate] = token
        if self.client is None:
            return
        try:
            self.client.hset(REDIS_HASH_KEY, predicate, token)
            self.client.expire(REDIS_HASH_KEY, TTL_SECONDS)
        except Exception as e:
            logger.warning("GroupingTypeCache write failed (not persisted): %s", e)


def _text(value):
    """Decode a Redis value to str (clients may return bytes or str)."""
    return value.decode("utf-8") if isinstance(value, bytes) else value
