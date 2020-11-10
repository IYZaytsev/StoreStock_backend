#!/bin/bash
#A script that starts the server
ENV=$1
if [ ! -d "./venv" ];
then
	echo "no venv found, creating one..."
	python3 -m venv ./venv
	echo "sourced env variables"
	source .env
	echo "installing dependencies"
	pip3 install -r requirements.txt
fi
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
	uwsgi --ini storestock_backend.ini
fi
