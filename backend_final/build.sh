#!/usr/bin/env bash
set -o errexit

# Install backend_final dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install skillsync-backend dependencies (mounted as sub-app)
SKILLSYNC_DIR="../skillsync-backend"
if [ -d "$SKILLSYNC_DIR" ]; then
    echo "Installing skillsync-backend dependencies..."
    # The skillsync-backend uses the same core libs; install any extras
    pip install requests pdfplumber python-dotenv
    echo "skillsync-backend dependencies installed."
fi

# Create required directories
mkdir -p uploads certificates
