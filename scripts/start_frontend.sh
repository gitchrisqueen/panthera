#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

# Navigate to the frontend directory
cd "$SCRIPT_DIR/../frontend"

# Install dependencies and start the frontend server
npm install
npm start