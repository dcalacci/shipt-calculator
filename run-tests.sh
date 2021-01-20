#!/usr/bin/env bash
docker run -e CONFIG='development' -e SECRET_KEY='dev' --entrypoint "python" -p 5000:5000 -v $PWD:/app shipt-receipts-dev:latest -m pytest
