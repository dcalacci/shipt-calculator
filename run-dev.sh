#!/usr/bin/env bash
#docker build -t "shipt-receipts-dev" .
docker run -e CONFIG='development' -p 5000:5000 -v $PWD:/app shipt-receipts-dev:latest
