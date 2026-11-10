"""Unit tests for label_resolver.py."""

import unittest
from unittest.mock import MagicMock, patch

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
        with self.assertLogs("integraality.label_resolver", level="WARNING") as cm:
            result = self._resolver().resolve(["Q142"])
        self.assertEqual(result["Q142"], "Q142")
        self.assertIn("network error", cm.output[0])

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

    def test_fetches_in_batches_of_50(self):
        ids = [f"Q{i}" for i in range(120)]
        self.repo.loadcontent.return_value = {}
        self._resolver().resolve(ids)
        # 120 ids → 3 batches: 50, 50, 20
        self.assertEqual(self.repo.loadcontent.call_count, 3)
        first_batch = self.repo.loadcontent.call_args_list[0][0][0]["ids"]
        self.assertEqual(len(first_batch), 50)
        last_batch = self.repo.loadcontent.call_args_list[2][0][0]["ids"]
        self.assertEqual(len(last_batch), 20)

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

    def test_warm_logs_warning_on_exception_and_does_not_raise(self):
        self.repo.loadcontent.side_effect = Exception("network error")
        cache = MagicMock()
        cache.get_cache_value.return_value = None
        # Should not raise (logs a warning instead).
        warm_label_cache({"P17"}, repo=self.repo, cache=cache)


class WarmLabelCachesFromDbTest(unittest.TestCase):
    @patch("integraality.label_resolver.warm_label_cache")
    @patch("integraality.label_resolver.DashboardRegistry")
    @patch("pywikibot.Site")
    @patch("redis.StrictRedis")
    def test_fetches_ids_from_db_and_warms(
        self, mock_redis, mock_site, mock_registry_cls, mock_warm
    ):
        from ..label_resolver import warm_label_caches_from_db

        mock_registry = MagicMock()
        mock_registry_cls.return_value.__enter__ = MagicMock(return_value=mock_registry)
        mock_registry_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_registry.list_all_label_ids.return_value = {"P17", "P18"}

        warm_label_caches_from_db()

        mock_warm.assert_called_once()
        ids = mock_warm.call_args[0][0]
        self.assertEqual(ids, {"P17", "P18"})
