#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Assemble Property dashboard configuration from template parameters.
"""

from .column import ColumnMaker, ColumnSyntaxException
from .grouping import GroupingConfigurationMaker
from .grouping_link import GroupingLinkSyntaxException
from .sparql_utils import SparqlEngineBuilder

REQUIRED_CONFIG_FIELDS = ["selector_sparql", "grouping_property", "properties"]
VALID_GROUPING_LINK_MODES = ("link", "create")


class ConfigAssemblyException(Exception):
    pass


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

    def parse_config(self, config):
        for field in REQUIRED_CONFIG_FIELDS:
            if field not in config:
                raise ConfigAssemblyException("A required field is missing: %s" % field)
        config["columns"] = self.parse_config_properties(config["properties"])
        del config["properties"]
        try:
            config["grouping_configuration"] = GroupingConfigurationMaker.make(
                config.pop("grouping_property"),
                config.pop("higher_grouping", None),
                int(config.pop("grouping_threshold", 20)),
                config.pop("grouping_link", None),
                config.pop("groupings", None),
            )
        except GroupingLinkSyntaxException as e:
            raise ConfigAssemblyException(e)
        config["stats_for_no_group"] = bool(config.get("stats_for_no_group", False))
        config["grouping_link_mode"] = config.pop("grouping_link_mode", "link")
        if config["grouping_link_mode"] not in VALID_GROUPING_LINK_MODES:
            raise ConfigAssemblyException(
                f"Unknown grouping_link_mode: {config['grouping_link_mode']}"
            )
        config["sparql_query_engine"] = SparqlEngineBuilder.make(
            config.pop("sparql_endpoint", None),
            site_url=self.site_url,
        )
        return config

    @staticmethod
    def parse_config_properties(properties_string):
        properties = [x.strip() for x in properties_string.split(",")]
        properties_data = []
        for prop in properties:
            try:
                (key, title) = prop.split(":")
            except ValueError:
                (key, title) = (prop, None)
            if key:
                try:
                    properties_data.append(ColumnMaker.make(key, title))
                except ColumnSyntaxException as e:
                    raise ConfigAssemblyException(e)
        return properties_data
