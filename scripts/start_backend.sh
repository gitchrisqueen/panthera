#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR=$(dirname "$0")

# Navigate to the frontend directory
cd "$SCRIPT_DIR/../backend"

# Install dependencies and start the backend server
pip install -r requirements.txt

# Load environment variables from .env file using python-dotenv
python -c 'from dotenv import load_dotenv; load_dotenv()'

# Run database migrations
python manage.py db upgrade

# Start the backend server
flask run