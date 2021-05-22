#!/bin/bash
#
# Script to update all dashboards on a given wiki
#
# How to use
# ./bin/run.sh <wiki> <arguments>
# All arguments after the first one are passed through to the Python script
#
# Example
# ./bin/run.sh meta https://meta.wikimedia.org

CURRENT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
. $CURRENT_DIR/defaults.sh

cd $SOURCE_PATH || exit

# Use a virtual environment with our requirements
source $VIRTUAL_ENV_PATH/bin/activate

WIKI="$1"
shift

echo_time "Starting update for $WIKI."

start_time="$(date -u +%s)"

python integraality/pages_processor.py "$@"

end_time="$(date -u +%s)"
elapsed_time="$((end_time-start_time))"
elapsed_time_ms=$(($elapsed_time * 1000))

metric="$STATSD_PREFIX.periodic_update.$WIKI"
echo "Sending metric $metric:$elapsed_time_ms to $STATSD_HOST:$STATSD_PORT"
echo -n "$metric:$elapsed_time_ms|ms" | nc -w 1 -u $STATSD_HOST $STATSD_PORT

echo_time "Done with the update for $WIKI! ($(TZ=UTC0 printf '%(%H:%M:%S)T\n' $elapsed_time)s)"
