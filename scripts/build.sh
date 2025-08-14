#!/bin/bash
# https://github.com/danlapid/python-workers-mcp/blob/main/scripts/build.sh

set -e

# Check if Python 3.12 is installed
if ! command -v python3.12 &> /dev/null; then
    echo "Error: Python 3.12 is required but not installed."
    exit 1
fi

# Create pyodide virtual environment if it doesn't exist
if [ ! -d ".venv-pyodide" ]; then
    echo "Creating pyodide virtual environment (.venv-pyodide)..."
    pyodide venv .venv-pyodide
else
    echo "Using existing pyodide virtual environment (.venv-pyodide)..."
fi

# Download vendored packages
echo "Installing vendored packages from vendor.txt..."
.venv-pyodide/bin/pip install -t src/vendor -r vendor.txt

echo "Build completed successfully!"
