#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Format integraality results.
"""


class ResultsFormatter:
    """Format groupings into WikiText table."""

    def __init__(
        self,
        columns,
        grouping_configuration,
        property_threshold=0,
        cell_template="Integraality cell",
    ):
        self.columns = columns
        self.grouping_configuration = grouping_configuration
        self.property_threshold = property_threshold
        self.cell_template = cell_template

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
        text += f'! colspan="{colspan}" |Top groupings (Minimum {self.grouping_configuration.grouping_threshold} items)\n'
        text += f'! colspan="{len(self.columns)}"|Top Properties (used at least {self.property_threshold} times per grouping)\n'
        text += "|-\n"

        if self.grouping_configuration.higher_grouping:
            text += "! \n"

        text += "! Name\n"
        text += "! Count\n"
        for column_entry in self.columns.values():
            text += column_entry.make_column_header()

        return text

    def _format_grouping(self, grouping_object, grouping_type=None):
        """Format one grouping row."""
        text = grouping_object.row_opener()
        text += grouping_object.format_header_cell(
            self.grouping_configuration, grouping_type
        )
        text += grouping_object.format_count_cell()
        for column_entry in self.columns.values():
            text += grouping_object.format_cell(column_entry, self.cell_template)
        return text
