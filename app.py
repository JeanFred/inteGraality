"""WSGI entry point for Toolforge.

Toolforge convention expects $HOME/www/python/src/app.py to expose
an ``app`` variable.  This thin wrapper imports it from the package
so that relative imports inside the package work correctly.
"""

from integraality.app import app  # noqa: F401
