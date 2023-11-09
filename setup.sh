#!/bin/bash

echo
echo -e "\033[94mBeginning the Blueberry setup...\033[0m"
echo "Please wait while we prepare everything for you."
echo

# Check if Python3 and pip are installed, and if not, exit with an error message
command -v python3 &>/dev/null || { echo "Error: Python3 is required but not found. Please install it."; exit 1; }
command -v pip &>/dev/null || { echo "Error: Pip is required but not found. Please install it."; exit 1; }

# Define the user's home directory dynamically
HOME_DIR=$(eval echo ~$USER)

# Set the directory path within the user's home directory
directory="$HOME_DIR/blueberry"

# If a previous installation is detected, offer to reinstall
if [ -d "$directory" ]; then
    echo -e "Previous installation detected at $directory."
    echo "Reinstalling will delete the current directory and its contents."
    read -p "Would you like to proceed with reinstalling? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Deleting the existing directory and reinstalling..."
        rm -rf "$directory"
        echo "Previous installation removed."
    else
        echo "Installation aborted."
        exit 1
    fi
fi

# Create the directory
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

# Check if the local bin directory exists, if not create it
LOCAL_BIN="$HOME_DIR/.local/bin"
mkdir -p "$LOCAL_BIN"

# Create a symbolic link in the local bin directory
ln -sf "$directory/blueberry.py" "$LOCAL_BIN/blueberry" || { echo "Error: Failed to create a symbolic link."; exit 1; }

# Add local bin directory to PATH if it's not already there
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    echo "export PATH=\"\$PATH:$LOCAL_BIN\"" >> "$HOME_DIR/.bashrc"
    echo "Local bin directory added to PATH. Please restart your terminal or source ~/.bashrc to apply changes."
fi

# Deactivate the virtual environment
deactivate

echo
echo "Setup completed successfully."
echo

# Check if user has a macvendors API token and update the config file
read -p "Do you have a macvendors API token? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Enter your macvendors API token: " macvendors_api_token
    echo "Updating the config file with the API token..."
    echo "[DEFAULT]" > config.me
    echo "CSV_FILE_PATH = ~/blueberry/detected.csv" >> config.me
    echo "API_TOKEN = $macvendors_api_token" >> config.me
else
    echo "Proceeding without macvendors API token..."
fi

echo
echo -e "Type '\033[94mblueberry\033[0m' to start scanning for Bluetooth devices."
echo "To stop the script, press Ctrl+C."
echo "The generated CSV file can be found at: $HOME/blueberry/detected.csv"
echo
