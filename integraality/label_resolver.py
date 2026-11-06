"""Resolve P/Q entity ids to human-readable labels via pywikibot."""

import re

_PQ_RE = re.compile(r"^[PQ]\d+$")
LABEL_TTL = 30 * 24 * 3600  # 30 days; labels are stable


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

    def _fetch(self, entity_ids):
        labels = {}
        try:
            result = self.repo.loadcontent({"ids": entity_ids}, "labels")
            for eid, data in result.items():
                lang_labels = data.get("labels", {})
                label = (
                    lang_labels.get(self.lang, {}).get("value")
                    or lang_labels.get("en", {}).get("value")
                    or eid
                )
                labels[eid] = label
        except Exception:
            pass

        for eid in entity_ids:
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
    except Exception:
        pass
