#!/bin/bash

# Function to display an error message and exit
function error_exit {
    echo "Error: $1"
    exit 1
}

# Function to check if a command is available or exit
function check_command {
    command -v $1 &>/dev/null || error_exit "$1 is required but not found. Please install it."
}

# Function to create a directory or exit
function create_directory {
    mkdir -p "$1" || error_exit "Failed to create the '$1' directory."
}

# Function to make a script executable or exit
function make_executable {
    chmod +x "$1" || error_exit "Failed to make the '$1' script executable."
}

# Function to download the oui.txt file
function download_oui {
    oui_url="https://standards-oui.ieee.org/oui/oui.txt"
    wget "$oui_url" -O "$directory/oui.txt" || error_exit "Failed to download oui.txt"
}

# Initialize variables
HOME_DIR=$(eval echo ~$USER)
directory="$HOME_DIR/blueberry"
LOCAL_BIN="$HOME_DIR/.local/bin"

# Check if required commands are available
check_command python3
check_command pip
check_command wget # Check for wget command

# Offer to reinstall if previous installation is detected
[ -d "$directory" ] && {
    echo -e "Previous installation detected at $directory."
    read -p "Would you like to proceed with reinstalling? (y/n): " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && error_exit "Installation aborted."
    echo "Deleting the existing directory and reinstalling..."
    rm -rf "$directory"
    echo "Previous installation removed."
}

# Create the directory
create_directory "$directory"

# Clone the GitHub repository
cd "$directory" || error_exit "Failed to change directory to '$directory'."
git clone https://github.com/yanniedog/blueberry.git . || error_exit "Failed to clone the repository."

# Create and activate a virtual environment
python3 -m venv venv || error_exit "Failed to create the virtual environment."
source venv/bin/activate || error_exit "Failed to activate the virtual environment."

# Install required Python packages
pip install -r requirements.txt || error_exit "Failed to install Python packages."

# Make the blueberry.py script executable
make_executable "blueberry.py"

# Create the blueberry-venv.sh wrapper script
cat > "$directory/blueberry-venv.sh" <<EOF
#!/bin/bash

# Define the actual directory of the blueberry installation
BLUEBERRY_DIR="$directory"

# Activate the virtual environment
source "\$BLUEBERRY_DIR/venv/bin/activate"

# Run the blueberry.py script
python "\$BLUEBERRY_DIR/blueberry.py"

# Deactivate the virtual environment when done
deactivate
EOF
make_executable "$directory/blueberry-venv.sh"

# Create the local bin directory if it doesn't exist
create_directory "$LOCAL_BIN"

# Update the symbolic link to point to the wrapper script
ln -sf "$directory/blueberry-venv.sh" "$LOCAL_BIN/blueberry" || error_exit "Failed to create a symbolic link."

# Add local bin directory to PATH if it's not already there
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    echo "export PATH=\"\$PATH:$LOCAL_BIN\"" >> "$HOME_DIR/.bashrc"
    echo "Local bin directory added to PATH. Please restart your terminal or source ~/.bashrc to apply changes."
else
    echo "Local bin directory already in PATH."
fi

# Deactivate the virtual environment
deactivate

# Prompt for macvendors API token and update the config file
while true; do
    read -p "Do you have a macvendors API token? (y/n): " -n 1 -r response
    echo
    case $response in
        [Yy])
            read -p "Enter your macvendors API token: " macvendors_api_token
            cat >"$directory/config.me" <<EOF
[DEFAULT]
CSV_FILE_PATH = $directory/detected.csv
API_TOKEN = $macvendors_api_token
EOF
            break
            ;;
        [Nn])
            echo "Proceeding without macvendors API token..."
            break
            ;;
        *)
            echo "Invalid input. Please enter 'y' for yes or 'n' for no."
            ;;


    esac
done

# Download the oui.txt file
download_oui

echo -e "\033[94mSetup completed successfully.\033[0m"
echo -e "Type '\033[94mblueberry\033[0m' to start scanning for Bluetooth devices."
echo "To stop the script, press Ctrl+C."
echo "The generated CSV file can be found at: $directory/detected.csv"

# Automatically source the updated .bashrc for the current session
if [ -f "$HOME_DIR/.bashrc" ]; then
    source "$HOME_DIR/.bashrc"
fi
