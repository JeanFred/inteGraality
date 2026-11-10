"""Resolve P/Q entity ids to human-readable labels via pywikibot."""

import logging
import re

from .dashboard_registry import DashboardRegistry

_PQ_RE = re.compile(r"^[PQ][1-9]\d*$")
LABEL_TTL = 30 * 24 * 3600  # 30 days; labels are stable


_logger = logging.getLogger(__name__)


def is_entity_id(token):
    return bool(_PQ_RE.match(token))


class LabelResolver:
    """Batch-resolve P/Q ids to labels, Redis-cached per (id, lang).

    Pass a pywikibot DataSite as `repo` and optionally a RedisCache instance.
    Non-P/Q tokens are returned as-is (no API call made for them).
    """

    def __init__(self, repo, cache=None, lang="en"):
        self.repo = repo
        self.cache = cache
        self.lang = lang

    def resolve(self, ids, cache_only=False):
        """Return a dict mapping each id to its label (falls back to the id).

        ids: iterable of strings (mix of P/Q ids and other tokens is fine).
        cache_only: if True, skip the API fetch entirely — cache misses fall
          back to the bare id. Use this in web requests to avoid blocking on
          pywikibot network calls; reserve the full fetch for bot-side warming.
        """
        ids = list(ids)
        entity_ids = [i for i in ids if is_entity_id(i)]

        result = {}
        to_fetch = []

        for eid in entity_ids:
            cached = self._cache_get(eid)
            if cached is not None:
                result[eid] = cached
            else:
                to_fetch.append(eid)

        if to_fetch and not cache_only:
            fetched = self._fetch(to_fetch)
            for eid, label in fetched.items():
                result[eid] = label
                if label != eid:
                    self._cache_set(eid, label)

        # Non-entity tokens and cache misses (in cache_only mode) pass through.
        for token in ids:
            if token not in result:
                result[token] = token

        return result

    BATCH_SIZE = 50

    def _fetch(self, entity_ids):
        labels = {}
        for i in range(0, len(entity_ids), self.BATCH_SIZE):
            batch = entity_ids[i : i + self.BATCH_SIZE]
            try:
                result = self.repo.loadcontent({"ids": batch}, "labels")
                for eid, data in result.items():
                    lang_labels = data.get("labels", {})
                    label = (
                        lang_labels.get(self.lang, {}).get("value")
                        or lang_labels.get("en", {}).get("value")
                        or eid
                    )
                    labels[eid] = label
                    _logger.debug("Resolved %s -> %r", eid, label)
            except Exception as e:
                _logger.warning("Label fetch failed for batch starting at %d: %s", i, e)

        for eid in entity_ids:
            if eid not in labels:
                _logger.debug("Fallback %s -> %r (not returned by API)", eid, eid)
            labels.setdefault(eid, eid)

        return labels

    def _cache_key(self, eid):
        return f"label:{self.lang}:{eid}"

    def _cache_get(self, eid):
        if self.cache is None:
            return None
        return self.cache.get_cache_value(self._cache_key(eid))

    def _cache_set(self, eid, label):
        if self.cache is None:
            return
        self.cache.set_cache_value(self._cache_key(eid), label, ttl=LABEL_TTL)


def warm_label_cache(ids, repo, cache, lang="en"):
    """Warm the Redis label cache for the given P/Q ids; silently ignores errors."""
    if not ids:
        return
    try:
        LabelResolver(repo=repo, cache=cache, lang=lang).resolve(ids, cache_only=False)
    except Exception as e:
        _logger.warning("Label cache warming failed: %s", e)


def warm_label_caches_from_db():
    """Warm the Redis label cache for all P/Q ids recorded in the DB.

    Imports of pywikibot and redis are deferred to avoid pulling those
    heavy dependencies into the module namespace — label_resolver is also
    used in lightweight paths (web requests, tests) that don't need them.
    """
    import pywikibot
    from redis import StrictRedis

    from .cache import RedisCache, redis_host

    _logger.info("Warming label cache from DB...")
    with DashboardRegistry() as registry:
        ids = registry.list_all_label_ids()
    _logger.info("Found %d id(s) to warm", len(ids))

    cache = RedisCache(StrictRedis(host=redis_host(), decode_responses=False))
    repo = pywikibot.Site("wikidata", "wikidata").data_repository()
    warm_label_cache(ids, repo=repo, cache=cache)
    _logger.info("Done (%d id(s))", len(ids))


def main():
    logging.basicConfig(level=logging.DEBUG)
    warm_label_caches_from_db()


if __name__ == "__main__":
    main()
