"""Parse an inteGraality report (the rendered wikitext table) back to objects.

The inverse of ResultsFormatter: given a dashboard revision's wikitext, recover
the per-grouping / per-column coverage counts and the totals row. Handles both
the modern ``{{Integraality cell|pct|count|column=..|grouping=..}}`` format and
the pre-Nov-2019 ``{{Coloured cell|pct|count}}`` era (positional params, no
grouping= marker, sometimes a linked count cell and a malformed <small> totals
heading).

The runs backfiller uses ``shape`` (entity_total / grouping_count /
column_count); the full grouping/cell data supports future run-to-run diffs
without storing cells (reconstruct from revision_id).
"""

import re
from dataclasses import dataclass, field

import mwparserfromhell

from .line import NoGroupGrouping, TotalsGrouping

# The totals row anchor, stable since the earliest dashboards. Anchoring here
# (never the heading text) survives the malformed "<small>...<small>:" of early
# revisions.
_SORTBOTTOM_RE = re.compile(r'\|-\s*class="sortbottom"')

# A count cell, bare "| 9004" or linked "| [[Foo/Bar|9004]]" (old grouping
# rows link the count). Salvaged from the parser branch's parse_count_from_wikitext.
_LINKED_COUNT_RE = re.compile(r"\[\[[^|\]]+\|(\d[\d,]*)\]\]")
_BARE_COUNT_RE = re.compile(r"^\|+\s*(\d[\d,]*)\s*$")

# Old-era cell: {{Coloured cell|pct|count}} — positional, no grouping= marker.
_CELL_TEMPLATE_NAMES = ("Integraality cell", "Coloured cell")


@dataclass(frozen=True)
class ParsedGrouping:
    """One report row: a grouping (or the totals/no-group row) and its cells."""

    title: str | None  # grouping= value (Q-id/year/URL/UNKNOWN_VALUE), or None
    count: int | None
    cells: dict[str, int | None] = field(default_factory=dict)  # column -> count

    def get_key(self):
        return self.title


@dataclass(frozen=True)
class ParsedReport:
    """A parsed report: the real groupings, plus the totals row if present.

    ``groupings`` excludes the totals row and the "No grouping" row (mirroring
    the live path's len(groupings)); ``totals`` is the sortbottom row;
    ``no_group`` is the "None"-titled row when present.
    """

    groupings: list[ParsedGrouping]
    totals: ParsedGrouping | None
    no_group: ParsedGrouping | None = None

    @property
    def entity_total(self):
        return self.totals.count if self.totals else None

    @property
    def grouping_count(self):
        return len(self.groupings) or None

    @property
    def column_count(self):
        """Number of tracked columns, from the totals row.

        Falls back to the widest grouping row when the totals row has no cells
        (some old revisions). That fallback is best-effort: an early ragged row
        (a grouping missing a trailing empty cell) can make the widest row
        disagree by one with what the live path recorded. Acceptable for a
        backfill; the modern totals-row path is exact.
        """
        if self.totals and self.totals.cells:
            return len(self.totals.cells)
        widths = [len(g.cells) for g in self.groupings if g.cells]
        return max(widths) if widths else None

    @property
    def shape(self):
        """(entity_total, grouping_count, column_count) — the backfiller's view."""
        return (self.entity_total, self.grouping_count, self.column_count)

    @property
    def grouping_counts_dict(self):
        """Dict of grouping key → count for all rows, or None if the report is empty.

        Returns None when no regular grouping titles were recoverable (e.g.
        old-era revisions where {{Coloured cell}} rows have no grouping= param
        and no {{Q|...}} name cell), to avoid a misleading entity_sum of 0.
        """
        result = {g.title: g.count for g in self.groupings}
        if not result:
            return None
        if self.no_group is not None:
            result[NoGroupGrouping.MARKER] = self.no_group.count
        if self.totals is not None:
            result[TotalsGrouping.MARKER] = self.totals.count
        return result


def _parse_count(text):
    """Count from a cell line: linked ``[[..|9004]]`` or bare ``| 9004``."""
    m = _LINKED_COUNT_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))
    m = _BARE_COUNT_RE.match(text.strip())
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def _cell_templates(row_text):
    """Yield (column, count, grouping) for each cell template in a row.

    Modern cells carry column=/grouping= named params; old {{Coloured cell}}
    cells are positional (pct, count) with neither — yielded as (None, count,
    None) so callers can still count columns.
    """
    code = mwparserfromhell.parse(row_text)
    for tpl in code.filter_templates():
        name = str(tpl.name).strip()
        if name not in _CELL_TEMPLATE_NAMES:
            continue
        if tpl.has("column"):
            column = str(tpl.get("column").value).strip()
        elif tpl.has("property"):
            column = str(tpl.get("property").value).strip()
        else:
            column = None
        grouping = (
            str(tpl.get("grouping").value).strip() if tpl.has("grouping") else None
        )
        # count is positional param "2" in both eras (pct is "1").
        count = None
        if tpl.has("2"):
            raw = str(tpl.get("2").value).strip()
            count = int(raw) if raw.isdigit() else None
        yield (column, count, grouping)


def _parse_header_columns(lines):
    """Extract ordered P-ids from {{Property|Pxxx}} header cells."""
    columns = []
    for ln in lines:
        if not ln.strip().startswith("!"):
            continue
        for tpl in mwparserfromhell.parse(ln).filter_templates():
            if str(tpl.name).strip().lower() == "property" and tpl.has("1"):
                pid = str(tpl.get("1").value).strip()
                if pid:
                    columns.append(pid)
    return columns


class ReportParser:
    """Parse an inteGraality report from its wikitext into a ParsedReport."""

    def parse(self, wikitext):
        """Parse ``wikitext`` into a :class:`ParsedReport` (empty if no table)."""
        if not wikitext:
            return ParsedReport(groupings=[], totals=None)

        lines = wikitext.splitlines()
        sortbottom_idx = next(
            (i for i, ln in enumerate(lines) if _SORTBOTTOM_RE.search(ln)), None
        )

        # Scope to the table that contains the sortbottom row.  On pages with
        # multiple tables (e.g. a Listeria list + a dashboard), we must not
        # bleed rows from other tables into the parse.  Find the {| opener that
        # precedes sortbottom_idx and the matching |} closer that follows it.
        if sortbottom_idx is not None:
            table_open = next(
                (
                    i
                    for i in range(sortbottom_idx, -1, -1)
                    if lines[i].strip().startswith("{|")
                ),
                0,
            )
            table_close = next(
                (
                    i
                    for i in range(sortbottom_idx, len(lines))
                    if lines[i].strip().startswith("|}")
                ),
                len(lines),
            )
            lines = lines[table_open : table_close + 1]
            sortbottom_idx = next(
                (i for i, ln in enumerate(lines) if _SORTBOTTOM_RE.search(ln)), None
            )

        # Extract column order from the header for old-era positional cells.
        header_columns = _parse_header_columns(lines)

        # Split the table body into row blocks on row openers ("|-").
        groupings = []
        totals = None
        no_group = None
        for start, end, is_totals in self._row_spans(lines, sortbottom_idx):
            row = self._parse_row(lines[start:end], header_columns)
            if row is None:
                continue
            if is_totals:
                totals = row
            elif self._is_real_grouping(row):
                groupings.append(row)
            elif self._is_no_group(row):
                no_group = row
        return ParsedReport(groupings=groupings, totals=totals, no_group=no_group)

    @staticmethod
    def _row_spans(lines, sortbottom_idx):
        """Yield (start, end, is_totals) line spans for each table row block."""
        # Row openers, plus table close, bound the blocks.
        openers = [i for i, ln in enumerate(lines) if ln.strip().startswith("|-")]
        close = next(
            (i for i, ln in enumerate(lines) if ln.strip().startswith("|}")),
            len(lines),
        )
        bounds = openers + [close]
        for a, b in zip(openers, bounds[1:]):
            yield (a + 1, b, a == sortbottom_idx)

    def _parse_row(self, row_lines, header_columns=None):
        """Parse one row block into a ParsedGrouping (or None if not a data row)."""
        row_text = "\n".join(row_lines)
        cells = {}
        title = None
        positional_counts = []
        for column, count, grouping in _cell_templates(row_text):
            if grouping and title is None:
                title = grouping
            if column is not None:
                cells[column] = count
            else:
                positional_counts.append(count)  # old {{Coloured cell}}, no column=

        n_columns = len(cells) or len(positional_counts)
        if n_columns == 0:
            return None  # header or a non-data row

        # Count cell is the first bare/linked integer cell in the row.
        count = None
        for ln in row_lines:
            count = _parse_count(ln)
            if count is not None:
                break

        # Old era has no grouping= marker; fall back to the {{Q|Q...}} name cell.
        if title is None:
            title = self._name_from_qid(row_lines)

        # Old-era positional cells: map counts to real column keys via the
        # header order when available; fall back to synthetic _0/_1 keys.
        if not cells and positional_counts:
            if header_columns and len(header_columns) >= len(positional_counts):
                cells = {
                    header_columns[i]: positional_counts[i]
                    for i in range(len(positional_counts))
                }
            else:
                cells = {
                    f"_{i}": positional_counts[i] for i in range(len(positional_counts))
                }
        return ParsedGrouping(title=title, count=count, cells=cells)

    @staticmethod
    def _name_from_qid(row_lines):
        """Old-era grouping name: the {{Q|Q...}} link in the name cell."""
        for ln in row_lines:
            m = re.search(r"\{\{Q\|(Q\d+)\}\}", ln)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _is_real_grouping(row):
        """Whether ``row`` is a real grouping (counted by the live path's
        len(groupings)). UNKNOWN_VALUE is real; the No-grouping row is not.

        The No-grouping row is excluded by two era-dependent paths, both
        landing on a falsy/"None" title: modern cells carry grouping=None (the
        NoGroupGrouping MARKER string, via get_key()), while old-era rows have
        no grouping= param and no {{Q|...}} name cell, so _name_from_qid returns
        None. Either way it fails this check.
        """
        return bool(row.title) and row.title != NoGroupGrouping.MARKER

    @staticmethod
    def _is_no_group(row):
        """Whether ``row`` is the "No grouping" row."""
        return row.title == NoGroupGrouping.MARKER
