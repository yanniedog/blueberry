#!/bin/bash

# Path to the directory where blueberry.py and the virtual environment are located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Activate the virtual environment
source "$DIR/venv/bin/activate"

# Run the blueberry.py script
python "$DIR/blueberry.py"

# Deactivate the virtual environment when done
deactivate
