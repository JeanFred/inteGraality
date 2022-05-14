inteGraality
============
[![Build Status](https://travis-ci.org/JeanFred/inteGraality.svg?branch=master)](https://travis-ci.org/JeanFred/inteGraality)
[![Coverage Status](https://codecov.io/github/JeanFred/inteGraality/coverage.svg?branch=master)](https://codecov.io/github/JeanFred/inteGraality?branch=master)[
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Generate dashboards of property coverage for a given part of Wikidata.

Lives on [Toolforge].

Testing
-------

Unit tests are executed through `tox`.

For a quick functional test:
```
docker-compose up -d
docker-compose run --rm web python3 integraality/property_statistics.py
```


Authors
-------

Based on an original idea by Maarten Dammers.


[Toolforge]: http://tools.wmflabs.org/integraality/
