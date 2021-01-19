#!/usr/bin/env bash
docker run --entrypoint="" -ti -e CONFIG="development" -e PYTHONPATH="." -v $PWD:/app shipt-receipts-dev:latest python scripts/get-images.py

