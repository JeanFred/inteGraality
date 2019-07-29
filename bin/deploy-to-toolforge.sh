#!/bin/bash
user="";
if [ -n "$1" ]; then
    user="$1"
fi

ansible-playbook -i deploy/hosts deploy/main.yml -vvv -u $user --diff
