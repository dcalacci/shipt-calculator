#!/usr/bin/env bash

# docker build -t "shipt-calculator"  -f Dockerfile .
docker run -e CONFIG='production' --env-file .env.prod -p 8080:8080 shipt-calculator:latest
