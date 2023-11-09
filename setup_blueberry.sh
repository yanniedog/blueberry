#!/bin/bash

# Function to display error message and exit
function display_error {
    echo "Error: $1"
    exit 1
}

# Check if Python3 and pip are installed
if ! command -v python3 &>/dev/null || ! command -v pip &>/dev/null; then
    display_error "Python3 and pip are required but not found. Please install them."
fi

# Clone the GitHub repository
if ! git clone https://github.com/yanniedog/bt.git; then
    display_error "Failed to clone the repository."
fi

# Change to the bt directory
cd bt || display_error "Failed to change directory to 'bt'."

# Create a virtual environment
python3 -m venv venv || display_error "Failed to create the virtual environment."

# Activate the virtual environment
source venv/bin/activate || display_error "Failed to activate the virtual environment."

# Install required Python packages
pip install -r requirements.txt || display_error "Failed to install Python packages."

# Deactivate the virtual environment
deactivate

echo "Setup completed successfully."
