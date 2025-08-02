#!/bin/bash
export DOCKER_HOSTNAME=$(hostname || scutil --get LocalHostName)
docker compose up -d

