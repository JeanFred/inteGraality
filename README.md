# inteGraality

![maintenance-status](https://img.shields.io/badge/maintenance-actively--developed-brightgreen.svg)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/JeanFred/inteGraality/refs/heads/master/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

[![Toolforge](https://img.shields.io/badge/hosted-Toolforge-990000.svg)](https://integraality.toolforge.org/)
[![Issues](https://img.shields.io/badge/issues-Phabricator-blue.svg)](https://phabricator.wikimedia.org/tag/tool-integraality/)

A tool that generates dashboards of property coverage for a given part of Wikidata.

Wikidata editors configure a dashboard by placing [`{{Property dashboard}}`](https://www.wikidata.org/wiki/Template:Property_dashboard) on a Wikidata (or Commons) page, defining an item selection, a grouping dimension, and properties to track. A bot ([User:InteGraalityBot](https://www.wikidata.org/wiki/Special:Contributions/InteGraalityBot)) then periodically uses SPARQL to query the coverage for each property, and updates the table on-wiki (or users can trigger an update manually).

Each cell in the dashboard links (via 🔍) to a live query showing exactly which items have or lack a given property — making it easy to find and fix gaps.

**Live instance:** <https://integraality.toolforge.org/>

## Documentation

- **User guide (how to create a dashboard):** [Wikidata:inteGraality](https://www.wikidata.org/wiki/Wikidata:inteGraality)
- **Template reference (all parameters):** [Template:Property dashboard](https://www.wikidata.org/wiki/Template:Property_dashboard)
- **Operations & architecture:** [Wikitech Tool:InteGraality](https://wikitech.wikimedia.org/wiki/Tool:InteGraality)

## How to get help and report issues

- Report issues or file feature requests on [Phabricator](https://phabricator.wikimedia.org/tag/tool-integraality/)
- Ask questions or get help at [Wikidata_talk:inteGraality](https://www.wikidata.org/wiki/Wikidata_talk:inteGraality)

## Development

### Technical overview

A cron job periodically loops through all dashboard pages, runs SPARQL queries (via [WDQS](https://query.wikidata.org/) or [QLever](https://qlever.dev/wikidata)) to compute property coverage, and writes results back as wikitext tables. A [Flask](https://flask.palletsprojects.com/) web app handles on-demand updates (`/update`) and generates the SPARQL queries behind the 🔍 links (`/queries`). Both use [pywikibot](https://www.mediawiki.org/wiki/Manual:Pywikibot) to read template configs from wiki pages and write results back. [Redis](https://redis.io/) caches parsed configs to speed up the query endpoint.

### Prerequisites

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose (for the full local stack)

### Running locally with Docker

```sh
docker compose up -d
```

This starts the Flask web app on <http://localhost:5000> and a Redis instance. Pages are written to `docker_pages/` instead of to the live wiki.

### Running tests

```sh
uv run pytest
```

### Project layout

```text
├── integraality/           # Python package (app, bot, tests)
├── bin/                    # Shell scripts for Toolforge jobs
├── conf/                   # Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Credits

Built and maintained by Jean-Frédéric.

Based on an original idea by Maarten Dammers.

## License

[MIT](LICENSE)
