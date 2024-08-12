#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

# Navigate to the frontend directory
cd "$SCRIPT_DIR/../backend"

# Install dependencies and start the backend server
pip install -r requirements.txt
flask run