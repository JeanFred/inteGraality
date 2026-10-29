"""Tests for config_backfiller: the full-history forward walk (T440134)."""

import unittest
from unittest.mock import MagicMock, patch

from ..config_backfiller import (
    ConfigBackfiller,
    build_config_facets_offline,
    extract_template_params,
)
from ..grouping_type_cache import GroupingTypeCache


class TestExtractTemplateParams(unittest.TestCase):
    def test_extracts_start_template_params(self):
        wikitext = (
            "Head\n{{Property dashboard\n|properties=P136,P404\n"
            "|grouping_property=P400\n|selector_sparql=wdt:P31 wd:Q7889\n}}\n"
            "{{Property dashboard end}}"
        )
        params = extract_template_params(wikitext)
        joined = "".join(params)
        self.assertIn("properties=P136,P404", joined)
        self.assertIn("grouping_property=P400", joined)

    def test_no_template_returns_none(self):
        self.assertIsNone(extract_template_params("just some content"))

    def test_marker_without_real_template_returns_none(self):
        # A bare mention with no closing braces does not parse to a template.
        self.assertIsNone(extract_template_params("see {{Property dashboard"))


class _Backfiller(ConfigBackfiller):
    """ConfigBackfiller with a stubbed revision stream (no network)."""

    def __init__(self, revisions):
        self._revisions = revisions
        self._hostname = "www.wikidata.org"

    @property
    def site_hostname(self):
        return self._hostname

    def _all_revisions(self, title):
        yield from self._revisions


def _wikitext(selector="wdt:P31 wd:Q5", props="P136"):
    return (
        f"{{{{Property dashboard\n|properties={props}\n"
        f"|grouping_property=P400\n|selector_sparql={selector}\n}}}}"
    )


class TestForwardWalk(unittest.TestCase):
    def setUp(self):
        self.config_assembler = MagicMock()
        # Use the real assembler for parsing (offline).
        from ..config_assembler import ConfigAssembler

        self.assembler = ConfigAssembler(site_url="https://www.wikidata.org/wiki/")

    def _registry(self):
        registry = MagicMock()
        # Each new config gets a fresh id so transitions are visible.
        registry.record_backfilled_configuration.side_effect = [1, 2, 3, 4]
        registry.link_run_to_configuration.return_value = True
        return registry

    def _run(self, revisions):
        backfiller = _Backfiller(revisions)
        backfiller.config_assembler = self.assembler
        # Pre-seed the grouping-type cache so resolution is a hit (no live
        # query): the fixtures all group by P400 -> predicate wdt:P400.
        cache = GroupingTypeCache()
        cache.set("wdt:P400", "item")
        backfiller.grouping_type_cache = cache
        registry = self._registry()
        configs, links = backfiller.backfill_dashboard(registry, "Dash", 7)
        return registry, configs, links

    def test_single_config_one_insert(self):
        # Human creates the config, then two bot runs under it.
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "Alice", False, _wikitext()),
            ("101", "2021-01-02T00:00:00Z", "InteGraalityBot", True, _wikitext()),
            ("102", "2021-01-03T00:00:00Z", "InteGraalityBot", True, _wikitext()),
        ]
        registry, configs, links = self._run(revisions)
        self.assertEqual(configs, 1)
        self.assertEqual(links, 2)
        # The config is attributed to the human authoring revision (100/Alice).
        _, kwargs = registry.record_backfilled_configuration.call_args
        self.assertEqual(kwargs["introduced_by_rev_id"], "100")
        self.assertEqual(kwargs["author"], "Alice")

    def test_config_change_inserts_second_row(self):
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "Alice", False, _wikitext(props="P136")),
            (
                "101",
                "2021-01-02T00:00:00Z",
                "InteGraalityBot",
                True,
                _wikitext("wdt:P31 wd:Q5", "P136"),
            ),
            ("102", "2021-01-03T00:00:00Z", "Bob", False, _wikitext(props="P136,P18")),
            (
                "103",
                "2021-01-04T00:00:00Z",
                "InteGraalityBot",
                True,
                _wikitext("wdt:P31 wd:Q5", "P136,P18"),
            ),
        ]
        _registry, configs, links = self._run(revisions)
        self.assertEqual(configs, 2)  # two distinct configs
        self.assertEqual(links, 2)  # two bot runs, each linked to the live config

    def test_bot_edit_before_any_config_is_not_linked(self):
        # A bot edit before any parseable config has no current_config_id.
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "InteGraalityBot", True, "no template"),
            ("101", "2021-01-02T00:00:00Z", "Alice", False, _wikitext()),
        ]
        registry, configs, links = self._run(revisions)
        self.assertEqual(configs, 1)
        self.assertEqual(links, 0)
        registry.link_run_to_configuration.assert_not_called()

    def test_unparseable_revision_does_not_advance_config(self):
        # A revision whose template is present but unparseable (missing required
        # fields) is skipped for transition; a following bot run stays unlinked
        # until a parseable config appears.
        broken = "{{Property dashboard\n|selector_sparql=wdt:P31 wd:Q5\n}}"
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "Alice", False, broken),
            ("101", "2021-01-02T00:00:00Z", "InteGraalityBot", True, broken),
        ]
        _registry, configs, links = self._run(revisions)
        self.assertEqual(configs, 0)
        self.assertEqual(links, 0)

    def test_bad_grouping_threshold_is_graceful_null(self):
        # A non-integer grouping_threshold now raises the typed
        # ConfigAssemblyException (in PARSER_DRIFT_ERRORS), so the walk treats it
        # as drift -- graceful NULL -- rather than crashing on a bare ValueError.
        bad = (
            "{{Property dashboard\n|properties=P136\n|grouping_property=P400\n"
            "|grouping_threshold=abc\n|selector_sparql=wdt:P31 wd:Q5\n}}"
        )
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "Alice", False, bad),
            ("101", "2021-01-02T00:00:00Z", "InteGraalityBot", True, bad),
        ]
        _registry, configs, links = self._run(revisions)
        self.assertEqual(configs, 0)
        self.assertEqual(links, 0)

    def test_commits_once_per_dashboard(self):
        revisions = [
            ("100", "2021-01-01T00:00:00Z", "Alice", False, _wikitext()),
        ]
        registry, _, _ = self._run(revisions)
        registry.conn.commit.assert_called_once()

    def test_non_drift_exception_surfaces(self):
        # A bug in facet extraction (not parser drift) must NOT be swallowed as
        # a graceful NULL -- it should propagate so the backfill fails loudly.
        backfiller = _Backfiller(
            [("100", "2021-01-01T00:00:00Z", "Alice", False, _wikitext())]
        )
        backfiller.config_assembler = self.assembler
        backfiller.grouping_type_cache = GroupingTypeCache()
        with (
            patch(
                "integraality.config_backfiller.build_config_facets_offline",
                side_effect=KeyError("facet bug"),
            ),
            self.assertRaises(KeyError),
        ):
            backfiller.backfill_dashboard(self._registry(), "Dash", 7)


class TestBuildConfigFacetsOffline(unittest.TestCase):
    SITE = "https://www.wikidata.org/wiki/"

    def _raw(self, **overrides):
        params = {
            "properties": "P136,P404",
            "grouping_property": "P400",
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
        }
        params.update(overrides)
        return params

    def test_builds_facets_without_live_resolution(self):
        facets = build_config_facets_offline(self._raw(), site_url=self.SITE)
        self.assertEqual(len(facets.config_hash), 64)
        # grouping_type is NULL offline (needs a live datatype query).
        self.assertIsNone(facets.grouping_type)
        # grouping_property is syntactic, predicate derived.
        self.assertEqual(facets.grouping_property, "P400")
        self.assertEqual(facets.grouping_predicate, "wdt:P400")
        self.assertEqual(facets.selector_mentions, ",P279,P31,Q7889,")
        self.assertEqual([c.property_id for c in facets.columns], ["P136", "P404"])

    def test_source_placeholder_contributes_no_column_row_but_feeds_hash(self):
        # A Pxxx(Qyyy) source cannot be expanded offline: no column rows for it,
        # but its authored key is still in the hash.
        with_source = build_config_facets_offline(
            self._raw(properties="P136,P1963(Q5)"), site_url=self.SITE
        )
        # Only the concrete P136 column gets a row.
        self.assertEqual([c.property_id for c in with_source.columns], ["P136"])
        # Hash differs from the plain two-property config (authored keys differ).
        plain = build_config_facets_offline(self._raw(), site_url=self.SITE)
        self.assertNotEqual(with_source.config_hash, plain.config_hash)

    def test_param_renames_normalized_before_hash(self):
        # properties -> columns, stats_for_no_group -> row_no_group are applied
        # by parse_config, so pre/post-rename params hash identically.
        pre = build_config_facets_offline(
            self._raw(properties="P136", stats_for_no_group="1"),
            site_url=self.SITE,
        )
        post_params = {
            "columns": "P136",
            "row_no_group": "1",
            "grouping_property": "P400",
            "selector_sparql": "wdt:P31/wdt:P279* wd:Q7889",
        }
        post = build_config_facets_offline(post_params, site_url=self.SITE)
        self.assertEqual(pre.config_hash, post.config_hash)

    def test_unparseable_raises(self):
        from ..config_assembler import ConfigAssemblyException

        with self.assertRaises(ConfigAssemblyException):
            build_config_facets_offline(
                {"selector_sparql": "wdt:P31 wd:Q5"},  # missing required fields
                site_url=self.SITE,
            )

    def test_cache_hit_resolves_type_without_a_query(self):
        # A preloaded predicate stamps grouping_type with no live query.
        cache = GroupingTypeCache()
        cache.set("wdt:P400", "year")
        with patch(
            "integraality.grouping.GroupingConfiguration._detect_grouping_type"
        ) as detect:
            facets = build_config_facets_offline(
                self._raw(), site_url=self.SITE, grouping_type_cache=cache
            )
        detect.assert_not_called()
        self.assertEqual(facets.grouping_type, "year")

    def test_cache_miss_resolves_live_then_caches(self):
        cache = GroupingTypeCache()
        from ..grouping import YearGroupingType

        with patch(
            "integraality.grouping.GroupingConfiguration._detect_grouping_type",
            return_value=YearGroupingType(),
        ) as detect:
            facets = build_config_facets_offline(
                self._raw(), site_url=self.SITE, grouping_type_cache=cache
            )
            # One live resolution...
            detect.assert_called_once()
            self.assertEqual(facets.grouping_type, "year")
            # ...then cached, so a second build for the same predicate is a hit.
            detect.reset_mock()
            build_config_facets_offline(
                self._raw(), site_url=self.SITE, grouping_type_cache=cache
            )
            detect.assert_not_called()

    def test_resolution_failure_leaves_null_and_is_not_cached(self):
        cache = GroupingTypeCache()
        with patch(
            "integraality.grouping.GroupingConfiguration._detect_grouping_type",
            side_effect=Exception("WDQS timeout"),
        ):
            facets = build_config_facets_offline(
                self._raw(), site_url=self.SITE, grouping_type_cache=cache
            )
        self.assertIsNone(facets.grouping_type)  # graceful NULL
        self.assertIsNone(cache.get("wdt:P400"))  # failure not cached (retryable)
