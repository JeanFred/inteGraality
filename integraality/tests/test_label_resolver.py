"""Unit tests for label_resolver.py."""

import unittest
from unittest.mock import MagicMock

from ..label_resolver import LABEL_TTL, LabelResolver, warm_label_cache


def _loadcontent_result(entries):
    """Build a fake loadcontent return value: {eid: {'labels': {lang: {'value': label}}}}."""
    return {
        eid: {"labels": {lang: {"value": val} for lang, val in labels.items()}}
        for eid, labels in entries.items()
    }


class LabelResolverTest(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()

    def _resolver(self, cache=None, lang="en"):
        return LabelResolver(repo=self.repo, cache=cache, lang=lang)

    def _loadcontent_returns(self, entries):
        self.repo.loadcontent.return_value = _loadcontent_result(entries)

    # --- basic resolution ---

    def test_resolves_item(self):
        self._loadcontent_returns({"Q142": {"en": "France"}})
        result = self._resolver().resolve(["Q142"])
        self.assertEqual(result["Q142"], "France")

    def test_resolves_property(self):
        self._loadcontent_returns({"P17": {"en": "country"}})
        result = self._resolver().resolve(["P17"])
        self.assertEqual(result["P17"], "country")

    def test_resolves_batch(self):
        self._loadcontent_returns({"Q142": {"en": "France"}, "P17": {"en": "country"}})
        result = self._resolver().resolve(["Q142", "P17"])
        self.assertEqual(result["Q142"], "France")
        self.assertEqual(result["P17"], "country")

    def test_non_entity_tokens_pass_through(self):
        result = self._resolver().resolve(["en", "enwiki", "2023"])
        self.assertEqual(result["en"], "en")
        self.assertEqual(result["enwiki"], "enwiki")
        self.assertEqual(result["2023"], "2023")
        self.repo.loadcontent.assert_not_called()

    def test_mixed_ids_and_tokens(self):
        self._loadcontent_returns({"P569": {"en": "date of birth"}})
        result = self._resolver().resolve(["P569", "en"])
        self.assertEqual(result["P569"], "date of birth")
        self.assertEqual(result["en"], "en")

    # --- fallback behaviour ---

    def test_falls_back_to_en_when_lang_missing(self):
        self._loadcontent_returns({"Q142": {"en": "France"}})
        result = self._resolver(lang="fr").resolve(["Q142"])
        self.assertEqual(result["Q142"], "France")

    def test_falls_back_to_id_when_no_labels(self):
        self._loadcontent_returns({"Q999": {}})
        result = self._resolver().resolve(["Q999"])
        self.assertEqual(result["Q999"], "Q999")

    def test_falls_back_to_id_when_entity_not_returned(self):
        self.repo.loadcontent.return_value = {}
        result = self._resolver().resolve(["Q404"])
        self.assertEqual(result["Q404"], "Q404")

    def test_falls_back_gracefully_on_exception(self):
        self.repo.loadcontent.side_effect = Exception("network error")
        result = self._resolver().resolve(["Q142"])
        self.assertEqual(result["Q142"], "Q142")

    # --- preferred lang ---

    def test_uses_requested_lang(self):
        self._loadcontent_returns({"Q142": {"en": "France", "fr": "La France"}})
        result = self._resolver(lang="fr").resolve(["Q142"])
        self.assertEqual(result["Q142"], "La France")

    # --- Redis caching ---

    def test_cache_hit_skips_api(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = "France"
        result = self._resolver(cache=cache).resolve(["Q142"])
        self.assertEqual(result["Q142"], "France")
        self.repo.loadcontent.assert_not_called()

    def test_cache_miss_fetches_and_stores(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        self._loadcontent_returns({"Q142": {"en": "France"}})
        result = self._resolver(cache=cache).resolve(["Q142"])
        self.assertEqual(result["Q142"], "France")
        cache.set_cache_value.assert_called_once_with(
            "label:en:Q142", "France", ttl=LABEL_TTL
        )

    def test_cache_key_includes_lang(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        self._loadcontent_returns({"Q142": {"fr": "France", "en": "France"}})
        self._resolver(cache=cache, lang="fr").resolve(["Q142"])
        cache.set_cache_value.assert_called_once_with(
            "label:fr:Q142", "France", ttl=LABEL_TTL
        )

    def test_fallback_id_not_cached(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        self.repo.loadcontent.return_value = {}
        self._resolver(cache=cache).resolve(["Q404"])
        cache.set_cache_value.assert_not_called()

    def test_no_cache_still_works(self):
        self._loadcontent_returns({"Q42": {"en": "Douglas Adams"}})
        result = self._resolver(cache=None).resolve(["Q42"])
        self.assertEqual(result["Q42"], "Douglas Adams")

    # --- loadcontent call ---

    def test_calls_loadcontent_with_ids_and_labels_prop(self):
        self._loadcontent_returns({"Q42": {"en": "Douglas Adams"}})
        self._resolver().resolve(["Q42"])
        self.repo.loadcontent.assert_called_once_with({"ids": ["Q42"]}, "labels")

    def test_empty_input(self):
        result = self._resolver().resolve([])
        self.assertEqual(result, {})
        self.repo.loadcontent.assert_not_called()


class CacheOnlyModeTest(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()

    def test_cache_only_returns_cached_label(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = "France"
        result = LabelResolver(repo=self.repo, cache=cache).resolve(
            ["Q142"], cache_only=True
        )
        self.assertEqual(result["Q142"], "France")

    def test_cache_only_falls_back_to_id_on_miss(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        result = LabelResolver(repo=self.repo, cache=cache).resolve(
            ["Q142"], cache_only=True
        )
        self.assertEqual(result["Q142"], "Q142")

    def test_cache_only_never_calls_loadcontent(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        LabelResolver(repo=self.repo, cache=cache).resolve(["Q142"], cache_only=True)
        self.repo.loadcontent.assert_not_called()


class WarmLabelCacheTest(unittest.TestCase):
    def setUp(self):
        self.repo = MagicMock()

    def _loadcontent_returns(self, entries):
        self.repo.loadcontent.return_value = _loadcontent_result(entries)

    def test_warm_populates_cache(self):
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        self._loadcontent_returns({"P17": {"en": "country"}})
        warm_label_cache({"P17"}, repo=self.repo, cache=cache)
        cache.set_cache_value.assert_called_once_with(
            "label:en:P17", "country", ttl=LABEL_TTL
        )

    def test_warm_empty_ids_is_noop(self):
        cache = MagicMock()
        warm_label_cache(set(), repo=self.repo, cache=cache)
        self.repo.loadcontent.assert_not_called()

    def test_warm_silently_ignores_exception(self):
        self.repo.loadcontent.side_effect = Exception("network error")
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        # Should not raise.
        warm_label_cache({"P17"}, repo=self.repo, cache=cache)
