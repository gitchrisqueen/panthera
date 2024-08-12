#!/bin/bash

#
# Copyright (c) 2024. Christopher Queen Consulting LLC (http://www.ChristopherQueenConsulting.com/)
#

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

# Navigate to the frontend directory
cd "$SCRIPT_DIR/.."

# Start Docker via Docker Compose in detached mode
docker-compose up --build -d --wait

sleep 5

# Open the main frontend app in the default browser
open http://localhost:3000

# Watch for source code changes and rebuild/refresh Dockerr containers
docker-compose watch