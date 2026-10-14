"""
Assemble Property dashboard configuration from template parameters.
"""

from .column import ColumnMaker, ColumnSyntaxException
from .config import ParsedConfig
from .grouping import GroupingConfigurationMaker
from .grouping_link import GroupingLinkSyntaxException
from .sparql_utils import SparqlEngineBuilder, UnsupportedSparqlEngineException

REQUIRED_CONFIG_FIELDS = ["selector_sparql", "grouping_property", "columns"]
VALID_GROUPING_LINK_MODES = ("link", "create")
PARAM_RENAMES = {
    "stats_for_no_group": "row_no_group",
    "properties": "columns",
}


class ConfigAssemblyException(Exception):
    pass


def _parse_bool_param(config, key, default=False):
    """Parse a template boolean: '1' → True, '0'/absent → False."""
    value = config.pop(key, None)
    if value is None:
        return default
    return value not in ("", "0")


class ConfigAssembler:
    def __init__(self, site_url):
        self.site_url = site_url

    @staticmethod
    def extract_elements_from_template_param(template_param):
        """Extract and sanitize the contents of a parsed template param."""
        (field, _, value) = template_param.partition("=")
        return (field.strip(), value.replace("{{!}}", "|"))

    def parse_config_from_params(self, params):
        return {
            key: value
            for (key, value) in [
                self.extract_elements_from_template_param(param) for param in params
            ]
            if key
        }

    @staticmethod
    def _parse_grouping_threshold(config):
        """Pop grouping_threshold as an int (default 20).

        A non-integer value is a config error, not an unclassified crash, so it
        raises ConfigAssemblyException (CONFIG category) rather than a bare
        ValueError from int().
        """
        raw = config.pop("grouping_threshold", 20)
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ConfigAssemblyException(
                f"grouping_threshold must be an integer, got {raw!r}"
            )

    @staticmethod
    def _apply_legacy_renames(config):
        """Migrate deprecated template param names to their canonical form.

        The canonical name wins if both are present (so an explicit `columns`
        beats a legacy `properties`).
        """
        for old, new in PARAM_RENAMES.items():
            if old in config:
                config.setdefault(new, config.pop(old))

    @staticmethod
    def _check_required_fields(config):
        for field in REQUIRED_CONFIG_FIELDS:
            if field not in config:
                raise ConfigAssemblyException(f"A required field is missing: {field}")

    @staticmethod
    def _assemble_grouping(config, grouping_threshold):
        try:
            return GroupingConfigurationMaker.make(
                config.pop("grouping_property"),
                config.pop("higher_grouping", None),
                grouping_threshold,
                config.pop("grouping_link", None),
                config.pop("groupings", None),
            )
        except GroupingLinkSyntaxException as e:
            raise ConfigAssemblyException(e)

    @staticmethod
    def _parse_grouping_link_mode(config):
        mode = config.pop("grouping_link_mode", "link")
        if mode not in VALID_GROUPING_LINK_MODES:
            raise ConfigAssemblyException(f"Unknown grouping_link_mode: {mode}")
        return mode

    def _assemble_engine(self, config):
        """Build the SPARQL engine, translating an unsupported endpoint into a
        ConfigAssemblyException (CONFIG category) rather than letting it surface
        as an unclassified failure.
        """
        try:
            return SparqlEngineBuilder.make(
                config.pop("sparql_endpoint", None),
                site_url=self.site_url,
            )
        except UnsupportedSparqlEngineException as e:
            raise ConfigAssemblyException(e) from e

    def parse_config(self, raw_params):
        # Work on a private copy: the body consumes keys via pop() as it builds,
        # so never mutate the caller's dict.
        config = dict(raw_params)
        self._apply_legacy_renames(config)
        self._check_required_fields(config)
        columns = self.parse_config_columns(config.pop("columns"))
        grouping_threshold = self._parse_grouping_threshold(config)
        grouping_configuration = self._assemble_grouping(config, grouping_threshold)
        row_no_group = _parse_bool_param(config, "row_no_group", default=False)
        row_totals = _parse_bool_param(config, "row_totals", default=True)
        grouping_link_mode = self._parse_grouping_link_mode(config)
        config.pop("property_threshold", None)
        sparql_query_engine = self._assemble_engine(config)
        return ParsedConfig(
            selector_sparql=config.get("selector_sparql"),
            columns=tuple(columns),
            grouping_configuration=grouping_configuration,
            sparql_query_engine=sparql_query_engine,
            row_no_group=row_no_group,
            row_totals=row_totals,
            grouping_link_mode=grouping_link_mode,
        )

    @staticmethod
    def parse_config_columns(columns_string):
        columns = [x.strip() for x in columns_string.split(",")]
        columns_data = []
        for column in columns:
            try:
                (key, title) = column.split(":")
            except ValueError:
                (key, title) = (column, None)
            if key:
                try:
                    columns_data.append(ColumnMaker.make(key, title))
                except ColumnSyntaxException as e:
                    raise ConfigAssemblyException(e)
        return columns_data
