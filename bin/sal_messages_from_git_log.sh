#!/bin/bash
# Generate SAL (Server Admin Log) messages from git log.
# Usage: sal_messages_from_git_log.sh <revision-range>

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: sal_messages_from_git_log.sh <revision-range>" >&2
    exit 1
fi

git log "$1" --reverse -C --no-merges \
    --format="Deploy %h (%s)%(trailers:key=Bug,valueonly,separator=%x2c )" \
    | sed -e 's/)T/) for T/' -e 's/`//g'
