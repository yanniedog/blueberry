#!/bin/bash

# Check if Python3 and pip are installed, and if not, exit with an error message
command -v python3 &>/dev/null || { echo "Error: Python3 is required but not found. Please install it."; exit 1; }
command -v pip &>/dev/null || { echo "Error: Pip is required but not found. Please install it."; exit 1; }

# Define the user's home directory dynamically
HOME_DIR=$(eval echo ~$USER)

# Set the directory path within the user's home directory
directory="$HOME_DIR/blueberry"

# Create the directory if it doesn't exist
mkdir -p "$directory" || { echo "Error: Failed to create the 'blueberry' directory."; exit 1; }

# Change to the blueberry directory
cd "$directory" || { echo "Error: Failed to change directory to '$directory'."; exit 1; }

# Clone the GitHub repository
git clone https://github.com/yanniedog/blueberry.git . || { echo "Error: Failed to clone the repository."; exit 1; }

# Create and activate a virtual environment
python3 -m venv venv || { echo "Error: Failed to create the virtual environment."; exit 1; }
source venv/bin/activate || { echo "Error: Failed to activate the virtual environment."; exit 1; }

# Install required Python packages
pip install -r requirements.txt || { echo "Error: Failed to install Python packages."; exit 1; }

# Make the blueberry.py script executable
chmod +x blueberry.py || { echo "Error: Failed to make the 'blueberry.py' script executable."; exit 1; }

# Create a symbolic link in /usr/local/bin
ln -sf "$directory/blueberry.py" /usr/local/bin/blueberry || { echo "Error: Failed to create a symbolic link."; exit 1; }

# Deactivate the virtual environment
deactivate

echo "Setup completed successfully."
