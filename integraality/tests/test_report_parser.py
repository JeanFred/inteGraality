"""Unit tests for report_parser.py."""

import unittest

from ..report_parser import ParsedReport, ReportParser

_MODERN = """\
{| class="wikitable sortable"
! colspan="2" |Top groupings
! colspan="2"|Top Properties
|-
! Name
! Count
|-
| {{Q|Q30}}
| 500
| {{Integraality cell|80|400|column=P21|grouping=Q30}}
| {{Integraality cell|60|300|column=P569|grouping=Q30}}
|-
| {{Q|Q145}}
| 300
| {{Integraality cell|90|270|column=P21|grouping=Q145}}
| {{Integraality cell|50|150|column=P569|grouping=Q145}}
|-
| {{int:wikibase-snakview-variations-somevalue-label}}
| 4
| {{Integraality cell|100|4|column=P21|grouping=UNKNOWN_VALUE}}
| {{Integraality cell|0|0|column=P569|grouping=UNKNOWN_VALUE}}
|-
|
| No grouping
| 200
| {{Integraality cell|33|66|column=P21|grouping=None}}
| {{Integraality cell|10|20|column=P569|grouping=None}}
|- class="sortbottom"
| '''Totals''' <small>(all items)</small>
| 39163
| {{Integraality cell|100|39163|column=P21|grouping=}}
| {{Integraality cell|100|39163|column=P569|grouping=}}
|}
"""

# Higher-grouping: config carries higher_grouping=, totals row prefixed "|| |".
_HIGHER_GROUPING = """\
{{Property dashboard |grouping_property=P175 |higher_grouping=wdt:P41 }}
{| class="wikitable sortable"
! colspan="3" |Top groupings
|-
!
! Name
! Count
|-
| flag
| {{Q|Q30}}
| 91765
| {{Integraality cell|25|23127|column=P175|grouping=Q30}}
|- class="sortbottom"
|| 
| '''Totals''' (all items)
| 309723
| {{Integraality cell|99|300000|column=P175|grouping=}}
|}
"""

# Old Coloured-cell era: positional params, no grouping=, linked count cells,
# malformed "<small>...<small>:" totals heading, "No grouping" plain-text row.
_OLD = """\
{| class="wikitable sortable"
|-
! Name
! Count
! data-sort-type="number"|{{Property|P136}}
! data-sort-type="number"|{{Property|P178}}
|-
| {{Q|Q1406}}
| [[Wikidata:.../Microsoft Windows|12297]] 
| {{Coloured cell|74.31|9138}}
| {{Coloured cell|58.35|7175}}
|-
| {{Q|Q10680}}
| [[Wikidata:.../PlayStation 2|2878]] 
| {{Coloured cell|76.09|2190}}
| {{Coloured cell|69.7|2006}}
|-
| No grouping 
| 6834 
| {{Coloured cell|12.88|880}}
| {{Coloured cell|5.71|390}}
|- class="sortbottom"
|'''Totals''' <small>(all items)<small>:
| 39702
| {{Coloured cell|63.95|25390}}
| {{Coloured cell|50.15|19912}}
|}
"""


# Intermediate era: named params but property= (not column=) and no grouping=
# on the totals row. Matches the original FindingGLAMs wikitext format.
_INTERMEDIATE = """\
{| class="wikitable sortable"
|-
! Name
! Count
|-
| {{Q|Q30}}
| 32740
| {{Integraality cell|63.1|20658|property=P625|grouping=Q30}}
| {{Integraality cell|95.96|31416|property=P131|grouping=Q30}}
|- class="sortbottom"
|'''Totals''' <small>(all items)</small>:
| 151112
| {{Integraality cell|70.04|105832|property=P625}}
| {{Integraality cell|84.58|127804|property=P131}}
|}
"""


class TestModernReport(unittest.TestCase):
    def setUp(self):
        self.report = ReportParser().parse(_MODERN)

    def test_shape(self):
        # 2 real groupings (Q30, Q145) + UNKNOWN_VALUE = 3; No-grouping excluded.
        self.assertEqual(self.report.shape, (39163, 3, 2))

    def test_groupings_exclude_nogroup_and_totals(self):
        titles = [g.title for g in self.report.groupings]
        self.assertEqual(titles, ["Q30", "Q145", "UNKNOWN_VALUE"])

    def test_cells_recovered_per_grouping(self):
        q30 = self.report.groupings[0]
        self.assertEqual(q30.cells, {"P21": 400, "P569": 300})

    def test_totals_row(self):
        self.assertEqual(self.report.totals.count, 39163)
        self.assertEqual(self.report.totals.cells, {"P21": 39163, "P569": 39163})

    def test_no_group_captured(self):
        self.assertIsNotNone(self.report.no_group)
        self.assertEqual(self.report.no_group.count, 200)

    def test_grouping_counts_dict(self):
        d = self.report.grouping_counts_dict
        self.assertEqual(d["Q30"], 500)
        self.assertEqual(d["Q145"], 300)
        self.assertEqual(d["UNKNOWN_VALUE"], 4)
        self.assertEqual(d["None"], 200)  # NoGroupGrouping key
        self.assertEqual(d[""], 39163)  # TotalsGrouping key


class TestHigherGrouping(unittest.TestCase):
    def test_shape_and_config_param_not_a_grouping(self):
        report = ReportParser().parse(_HIGHER_GROUPING)
        # entity_total past the "|| |" prefix; only Q30 is a grouping (not the
        # higher_grouping=wdt:P41 config param); 1 column.
        self.assertEqual(report.shape, (309723, 1, 1))
        self.assertEqual([g.title for g in report.groupings], ["Q30"])

    def test_count_cell_selected_past_higher_grouping_cell(self):
        """The count comes from the bare count cell (91765), not the {{Q|Q30}}
        higher-grouping name cell that precedes it, and cells are recovered."""
        q30 = ReportParser().parse(_HIGHER_GROUPING).groupings[0]
        self.assertEqual(q30.count, 91765)
        self.assertEqual(q30.cells, {"P175": 23127})


class TestOldColouredCellEra(unittest.TestCase):
    def setUp(self):
        self.report = ReportParser().parse(_OLD)

    def test_shape(self):
        # entity_total from bare totals count; 2 Q-groupings (No grouping
        # excluded); 2 columns.
        self.assertEqual(self.report.shape, (39702, 2, 2))

    def test_grouping_names_from_qid_fallback(self):
        self.assertEqual([g.title for g in self.report.groupings], ["Q1406", "Q10680"])

    def test_linked_count_cell_parsed(self):
        # The first grouping's count came from a [[link|12297]] cell.
        self.assertEqual(self.report.groupings[0].count, 12297)


class TestIntermediateEra(unittest.TestCase):
    """Intermediate era: property= (not column=) with grouping= on regular rows
    but no grouping= on the totals row. Totals ParsedGrouping.title must be
    None (not a string) so callers can substitute TotalsGrouping.MARKER."""

    def setUp(self):
        self.report = ReportParser().parse(_INTERMEDIATE)

    def test_shape(self):
        self.assertEqual(self.report.shape, (151112, 1, 2))

    def test_grouping_recovered(self):
        self.assertEqual(self.report.groupings[0].title, "Q30")
        self.assertEqual(self.report.groupings[0].cells, {"P625": 20658, "P131": 31416})

    def test_totals_title_is_none(self):
        """Totals row has no grouping= → title stays None."""
        self.assertIsNone(self.report.totals.title)

    def test_totals_cells_recovered(self):
        self.assertEqual(self.report.totals.cells, {"P625": 105832, "P131": 127804})

    def test_grouping_counts_dict_uses_totals_marker(self):
        d = self.report.grouping_counts_dict
        self.assertIn("", d)  # TotalsGrouping.MARKER
        self.assertEqual(d[""], 151112)


# Multi-table page: a Listeria-style wikitable followed by a dashboard table.
# The Listeria table uses wikilinks ([[Q30|...]]) not {{Q|}} templates. The
# real bug: _row_spans used the first |} as table close, scoping to the
# Listeria table entirely and missing the dashboard rows (entity_total = None,
# no groupings, no cells).
_MULTI_TABLE = """\
{| class="wikitable sortable"
|-
| [[Q30|United States]]
| [[Q145|United Kingdom]]
|}
{| class="wikitable sortable"
|-
! Name
! Count
|-
| {{Q|Q30}}
| 500
| {{Integraality cell|80|400|column=P21|grouping=Q30}}
|-
| {{Q|Q145}}
| 300
| {{Integraality cell|90|270|column=P21|grouping=Q145}}
|- class="sortbottom"
| '''Totals''' <small>(all items)</small>
| 800
| {{Integraality cell|84|672|column=P21|grouping=}}
|}
"""


class TestMultiTablePage(unittest.TestCase):
    """Pages with a non-dashboard wikitable before the dashboard table must
    only parse the dashboard table (the one containing sortbottom)."""

    def setUp(self):
        self.report = ReportParser().parse(_MULTI_TABLE)

    def test_shape(self):
        self.assertEqual(self.report.shape, (800, 2, 1))

    def test_groupings_from_dashboard_table_only(self):
        titles = [g.title for g in self.report.groupings]
        self.assertEqual(titles, ["Q30", "Q145"])


class TestEdgeCases(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(ReportParser().parse("").shape, (None, None, None))
        self.assertEqual(ReportParser().parse(None).shape, (None, None, None))

    def test_no_table_is_empty_report(self):
        report = ReportParser().parse("just some prose, no table")
        self.assertIsInstance(report, ParsedReport)
        self.assertEqual(report.shape, (None, None, None))

    def test_grouping_counts_dict_empty_returns_none(self):
        report = ReportParser().parse("")
        self.assertIsNone(report.grouping_counts_dict)

    def test_no_group_none_when_absent(self):
        report = ReportParser().parse(_HIGHER_GROUPING)
        self.assertIsNone(report.no_group)


if __name__ == "__main__":
    unittest.main()
