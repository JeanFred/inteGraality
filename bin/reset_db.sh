#!/bin/bash
#
# Drop and recreate the dashboard registry table.
# Intended to be run when schema.sql changes during deploy.
#
# After dropping, calls ensure_schema() to apply the new schema.
#

set -o errexit
set -o pipefail
set -o nounset

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$CURRENT_DIR/defaults.sh"

cd "$SOURCE_PATH" || exit

set +u
source "$VIRTUAL_ENV_PATH/bin/activate"
set -u

echo_time "Dropping dashboards table..."
mysql --defaults-file="$HOME/replica.my.cnf" -h "${DB_SERVER}" "${DB_NAME}" -e "DROP TABLE IF EXISTS dashboards;"

echo_time "Recreating schema..."
python -c "from integraality.db import get_connection, ensure_schema; ensure_schema(get_connection())"

echo_time "Done."
