#!/bin/bash
#
# Script to update the JSON database

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $CURRENT_DIR/defaults.sh

cd $SOURCE_PATH || exit

# Use a virtual environment with our requirements
source $VIRTUAL_ENV_PATH/bin/activate

echo_time "Starting update."

python pages_processor.py "$@"

echo_time "Done with the update!"
