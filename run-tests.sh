#!/usr/bin/env bash
docker run -e CONFIG='development' \
           -e SECRET_KEY='dev'     \
           --env-file .env         \
           --entrypoint "python"   \
           -p 5002:5000                           \
           -v $PWD:/app shipt-receipts-dev:latest \
           -m pytest
