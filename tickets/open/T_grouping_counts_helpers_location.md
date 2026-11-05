# Move grouping_counts blob helpers out of dashboard_registry

- URL: (not yet filed on Phabricator)
- Status: Open
- Priority: Needs Triage
- Created: 2026-11-05

## Description

`grouping_counts_to_entity_sum` and `grouping_counts_to_no_group` in
`dashboard_registry.py` are pure JSON-blob parsing helpers with no registry
coupling. They happen to live in the registry module for proximity to the
registry reads, but they're imported directly into `app.py` too, which creates
a mild coupling smell.

They would sit more naturally in a dedicated `blob_utils.py` or alongside the
`report_parser.py` data contract (which defines the key convention). No
behavioural change needed — pure move + import update.

Deferred because there's no obvious single right home without creating a new
file, and the current placement is functional.
