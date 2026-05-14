# Contributing

## Reporting issues

Bug reports and feature requests are welcome. Please file them on [Phabricator](https://phabricator.wikimedia.org/maniphest/task/create/?projects=tool-integraality).

For bugs, please include:

- The dashboard page URL
- What you expected vs. what happened
- Any error message shown on the page

For questions or discussion, use [Wikidata_talk:inteGraality](https://www.wikidata.org/wiki/Wikidata_talk:inteGraality).

## Development setup

### With Docker (recommended)

```sh
docker compose up -d
```

This gives you the Flask app on <http://localhost:5000> and Redis. Pages are written to `docker_pages/` instead of the live wiki.

### Without Docker

```sh
PYWIKIBOT_NO_USER_CONFIG=1 LOCAL_WRITE_PATH=docker_pages uv run flask --app integraality.app run
```

This runs the web app without Redis (the cache will miss and fall back to fetching from the wiki). Sufficient for working on templates or the query endpoint.

### Running tests

Unit tests (work offline, as they use fakeredis and mock pywikibot):

```sh
uv run pytest
```

Run a single test file:

```sh
uv run pytest integraality/tests/test_property_statistics.py
```

Functional test (runs a full update against the live wiki, writes to `docker_pages/`):

```sh
docker compose up -d
docker compose run --rm web python -m integraality.pages_processor https://www.wikidata.org/wiki/
```

## Dependencies

This project is managed with [uv](https://docs.astral.sh/uv/). To add a dependency:

```sh
uv add <package>        # runtime
uv add --dev <package>  # dev only
```

The pre-commit hook automatically regenerates `requirements.txt` and `requirements-dev.txt`.

## Code style

This project uses [ruff](https://docs.astral.sh/ruff/) for formatting and linting Python code. This is enforced via [pre-commit hooks](https://pre-commit.com/).

## Architecture overview

The data flow is:

1. A user places `{{Property dashboard}}` on a wiki page with config parameters
1. `PagesProcessor` reads the page (via pywikibot), parses the template config
1. `PropertyStatistics` runs SPARQL queries to compute coverage and formats the results as a wikitext table
1. The table is written back to the wiki page (or to `docker_pages/` locally)

The stack uses [Flask](https://flask.palletsprojects.com/) for the web app, [pywikibot](https://www.mediawiki.org/wiki/Manual:Pywikibot) for wiki interaction, [Redis](https://redis.io/) for caching, and [WDQS](https://query.wikidata.org/)/[QLever](https://qlever.dev/wikidata) as SPARQL backends.

Key modules:

| Module | Role |
| ------ | ---- |
| `app.py` | Flask web app — `/update`, `/queries` endpoints |
| `pages_processor.py` | Orchestration — reads wiki pages, triggers updates |
| `config_assembler.py` | Assembles dashboard configuration from template parameters |
| `property_statistics.py` | Core logic — builds SPARQL queries, processes results |
| `sparql_utils.py` | SPARQL engine abstraction (WDQS and QLever) |
| `column.py` | Column types (property, label, description, sitelink) |
| `grouping.py` | Grouping configuration and types |
| `line.py` | Row types (item grouping, year grouping, totals, etc.) |
| `results_formatter.py` | Wikitext table formatting |
| `page_saving.py` | Writing results to wiki or local files |
| `cache.py` | Redis cache for parsed configs |
| `sse.py` | Server-Sent Events for live update progress |

## Commit conventions

We follow conventions reminiscent of [OpenStack’s best practices](https://wiki.openstack.org/wiki/GitCommitMessages) and [MediaWiki’s guidelines](https://www.mediawiki.org/wiki/Gerrit/Commit_message_guidelines).

- Subject line: imperative mood, ~50 chars ("Add X", "Fix Y", not "Added X")
- Body: explain *why*, not just *what* − the diff shows what changed
- Reference relevant Phabricator tasks with a Git trailer `Bug: T123456`
- When removing or changing old code, include git archaeology (when it was introduced, why it existed) to help future readers understand the history
