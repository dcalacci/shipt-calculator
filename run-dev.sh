#!/usr/bin/env bash

# set env vars
# build docker container
docker build -t "shipt-calculator-dev" -f Dockerfile.dev .
docker run -e CONFIG='development' --env-file .env -p 5000:5000 -v $PWD:/app shipt-calculator-dev:latest
