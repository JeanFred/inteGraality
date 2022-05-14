echo_time() {
    echo "$(date +%F_%T) $*"
}

# Paths
: ${SOURCE_PATH:=$HOME/integraality}
: ${TOOLFORGE_PATH:=$HOME/www/python/}
: ${VIRTUAL_ENV_PATH:=$TOOLFORGE_PATH/venv}
: ${APP_PATH:=$TOOLFORGE_PATH/src}
: ${STATSD_HOST:=cloudmetrics1001.eqiad.wmnet}
: ${STATSD_PORT:=8125}
: ${STATSD_PREFIX:=toolforge.integraality}
