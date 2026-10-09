"""Canonical config serialization and hashing.

Field order, separators, None/empty token, boolean encoding and column-key join
are a frozen contract guarded by a golden-hash test -- change them deliberately.
"""

import hashlib

NONE_TOKEN = ""

_FIELD_SEP = "\x1f"
_COLUMN_SEP = "\x1e"


def canonical_token_bag(tokens):
    """Comma-padded ``",a,b,"`` bag (sorted, deduped), or None if empty."""
    cleaned = sorted({t.strip() for t in tokens if t and t.strip()})
    if not cleaned:
        return None
    return "," + ",".join(cleaned) + ","


def _bool_token(value):
    return "1" if value else "0"


def _opt(value):
    if value is None or value == "":
        return NONE_TOKEN
    return str(value)


def serialize_config(
    *,
    selector_sparql,
    grouping_property,
    grouping_threshold,
    higher_grouping,
    groupings,
    row_totals,
    row_no_group,
    grouping_link_mode,
    column_keys,
):
    """Canonical hash input. grouping_property/groupings are RAW params;
    column_keys are the PRE-expansion authored keys in order."""
    fields = [
        selector_sparql or "",
        _opt(grouping_property),
        str(grouping_threshold),
        _opt(higher_grouping),
        _opt(groupings),
        _bool_token(row_totals),
        _bool_token(row_no_group),
        grouping_link_mode or "",
        _COLUMN_SEP.join(column_keys),
    ]
    return _FIELD_SEP.join(fields)


def compute_config_hash(**kwargs):
    """sha256 hex of serialize_config(**kwargs)."""
    serialized = serialize_config(**kwargs)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
