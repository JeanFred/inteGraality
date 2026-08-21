echo_time() {
    echo "$(date +%F_%T) $*"
}

# Paths
: ${SOURCE_PATH:=$HOME/integraality}
: ${TOOLFORGE_PATH:=$HOME/www/python/}
: ${VIRTUAL_ENV_PATH:=$TOOLFORGE_PATH/venv}
: ${APP_PATH:=$TOOLFORGE_PATH/src}

# Database config
: ${DB_NAME:=s54041__integraality}
: ${DB_SERVER:=tools.db.svc.wikimedia.cloud}
