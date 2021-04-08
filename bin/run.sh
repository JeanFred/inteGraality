#!/bin/bash
#
# Script to update the JSON database

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $CURRENT_DIR/defaults.sh

cd $SOURCE_PATH || exit

# Use a virtual environment with our requirements
source $VIRTUAL_ENV_PATH/bin/activate

echo_time "Starting update."

start_time="$(date -u +%s)"

python integraality/pages_processor.py "$@"

end_time="$(date -u +%s)"
elapsed_time="$((end_time-start_time))"

echo_time "Done with the update! ($(TZ=UTC0 printf '%(%H:%M:%S)T\n' $elapsed_time)s)"
