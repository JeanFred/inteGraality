"""Pytest configuration for integraality tests."""

from unittest.mock import MagicMock, patch

import pywikibot.site

# Mock pywikibot.Site BEFORE any imports
mock_site_instance = MagicMock(spec=pywikibot.site.DataSite)
mock_site_instance.code = "wikidata"
mock_site_instance.sitename = "wikidata:wikidata"
mock_site_instance.data_repository.return_value = mock_site_instance

pywikibot_site_patcher = patch("pywikibot.Site", return_value=mock_site_instance)
pywikibot_site_patcher.start()
