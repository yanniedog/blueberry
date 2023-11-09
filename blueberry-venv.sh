#!/bin/bash

# Define the actual directory of the blueberry installation
BLUEBERRY_DIR="$HOME/blueberry"

# Activate the virtual environment
source "$BLUEBERRY_DIR/venv/bin/activate"

# Run the blueberry.py script
python "$BLUEBERRY_DIR/blueberry.py"

# Deactivate the virtual environment when done
deactivate
