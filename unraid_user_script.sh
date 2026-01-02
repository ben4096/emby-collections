#!/bin/bash
#
# Emby Collections Sync - Unraid User Script
#
# Installation:
# 1. Copy this script to /boot/config/plugins/user.scripts/scripts/emby-collections/script
# 2. Make it executable: chmod +x script
# 3. Update the paths and configuration below
# 4. Run manually or set a schedule in User Scripts plugin
#

# ============================================================================
# CONFIGURATION - MODIFY THESE PATHS
# ============================================================================

# Path where you want to install the script (persistent location on Unraid)
INSTALL_DIR="/mnt/user/appdata/emby-collections"

# Your config file location (will be created if doesn't exist)
CONFIG_FILE="${INSTALL_DIR}/config.yaml"

# Git repository URL (change only if you forked the repo)
REPO_URL="https://github.com/ben4096/emby-collections.git"

# Python binary location (Unraid default after installing Python 3)
PYTHON_BIN="/usr/bin/python3"

# ============================================================================
# DO NOT MODIFY BELOW THIS LINE
# ============================================================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Check if Python 3 is installed
if [ ! -f "$PYTHON_BIN" ]; then
    error "Python 3 not found at $PYTHON_BIN"
    error "Please install Python 3 from Unraid NerdTools or Community Applications"
    exit 1
fi

log "Python 3 found: $($PYTHON_BIN --version)"

# Create installation directory if it doesn't exist
if [ ! -d "$INSTALL_DIR" ]; then
    log "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

cd "$INSTALL_DIR" || exit 1

# Clone or update repository
if [ ! -d "$INSTALL_DIR/.git" ]; then
    log "Cloning repository..."
    git clone "$REPO_URL" temp_repo
    if [ $? -eq 0 ]; then
        mv temp_repo/* temp_repo/.* "$INSTALL_DIR/" 2>/dev/null
        rm -rf temp_repo
        log "Repository cloned successfully"
    else
        error "Failed to clone repository"
        exit 1
    fi
else
    log "Updating repository..."
    git pull
fi

# Setup virtual environment
VENV_DIR="${INSTALL_DIR}/venv"
if [ ! -d "$VENV_DIR" ]; then
    log "Creating virtual environment..."
    $PYTHON_BIN -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        error "Failed to create virtual environment"
        error "Make sure python3-venv is installed"
        exit 1
    fi
    log "Virtual environment created"
fi

# Activate virtual environment
log "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
log "Upgrading pip..."
pip install --upgrade pip

# Install/update dependencies
log "Installing dependencies..."
if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    pip install -r "$INSTALL_DIR/requirements.txt"
    if [ $? -ne 0 ]; then
        error "Failed to install dependencies"
        exit 1
    fi
else
    error "requirements.txt not found"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    warn "Config file not found: $CONFIG_FILE"
    if [ -f "$INSTALL_DIR/config.yaml.example" ]; then
        log "Creating config from example..."
        cp "$INSTALL_DIR/config.yaml.example" "$CONFIG_FILE"
        warn "Please edit $CONFIG_FILE with your settings before running again"
        exit 0
    else
        error "config.yaml.example not found"
        exit 1
    fi
fi

# Run the sync
log "Starting Emby Collections Sync..."
log "Config: $CONFIG_FILE"
log "="

python "$INSTALL_DIR/emby_collections.py" --config "$CONFIG_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    log "Sync completed successfully"
else
    error "Sync failed with exit code $EXIT_CODE"
fi

# Deactivate virtual environment
deactivate

exit $EXIT_CODE
