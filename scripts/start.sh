#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

# Start the frontend and backend servers
"$SCRIPT_DIR/start_frontend.sh" &
"$SCRIPT_DIR/start_backend.sh" &

# Wait for a few seconds to ensure servers are up
sleep 5

# Open the main frontend app in the default browser
open http://localhost:3000