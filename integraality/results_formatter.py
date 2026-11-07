"""Results formatting as wikitext table."""


class ResultsFormatter:
    """Format groupings into WikiText table."""

    def __init__(
        self,
        columns,
        grouping_configuration,
        cell_template="Integraality cell",
        count_diffs=None,
        rank_diffs=None,
    ):
        self.columns = columns
        self.grouping_configuration = grouping_configuration
        self.cell_template = cell_template
        # {grouping_key: int | None} — delta from previous run count; None for new entries.
        self.count_diffs = count_diffs or {}
        # {grouping_key: (curr_rank, prev_rank)} — None prev_rank means new entry.
        self.rank_diffs = rank_diffs or {}
        if self.rank_diffs and not self.count_diffs:
            raise ValueError(
                "rank_diffs requires count_diffs — both must be populated together"
            )

    @property
    def _has_diffs(self):
        return bool(self.count_diffs or self.rank_diffs)

    def format_report(self, groupings):
        """Format groupings into WikiText table.

        Args:
            groupings: list of Grouping objects (sorted by caller, may include NoGroupGrouping and TotalsGrouping)

        Returns:
            WikiText string
        """
        text = self._format_header()

        for grouping in groupings:
            text += self._format_grouping(grouping)

        text += "|}\n"
        return text

    def _format_header(self):
        text = '{| class="wikitable sortable"\n'
        colspan = 3 if self.grouping_configuration.higher_grouping else 2
        if self._has_diffs:
            colspan += 2
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_configuration.grouping_threshold} items)\n'
        if self.columns:
            text += f'! colspan="{len(self.columns)}"|Top Properties\n'
        text += "|-\n"

        if self._has_diffs:
            text += "! Pos\n"

        if self.grouping_configuration.higher_grouping:
            text += "! \n"

        text += "! Name\n"
        text += "! Count\n"

        if self._has_diffs:
            text += "! Δ\n"

        for column_entry in self.columns.values():
            text += column_entry.make_column_header()

        return text

    def _format_grouping(self, grouping_object, grouping_type=None):
        """Format one grouping row."""
        key = grouping_object.get_key()
        text = grouping_object.row_opener()
        if self._has_diffs:
            rank_entry = self.rank_diffs.get(key)
            if rank_entry is not None:
                curr_rank, prev_rank = rank_entry
                text += grouping_object.format_position_cell(curr_rank, prev_rank)
            else:
                text += "| \n"
        text += grouping_object.format_header_cell(
            self.grouping_configuration, grouping_type
        )
        text += grouping_object.format_count_cell()
        if self._has_diffs:
            text += grouping_object.format_diff_cell(self.count_diffs.get(key))
        for column_entry in self.columns.values():
            text += grouping_object.format_cell(column_entry, self.cell_template)
        return text
