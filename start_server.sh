#!/bin/bash
#A script that starts the server
ENV=$1
source .env
source .keys
echo "sourced env variables"
if [ "$ENV" == "local" ];
then
	echo "Local DEVELOPMENT: starting server..."
	python3 -m flask run -h 0.0.0.0 -p 5000
fi

if [ "$ENV" == "server" ];
then
	uwsgi --ini bridge_backend.ini
fi
