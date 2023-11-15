#!/bin/bash

# Function to display an error message and exit
function error_exit {
    echo "Error: $1" >&2
    exit 1
}

# Function to check if a command is available or install it
function check_or_install_command {
    if ! command -v $1 &>/dev/null; then
        echo "$1 not found, attempting to install..."
        sudo apt-get install -y $1 || error_exit "Failed to install $1."
    fi
}

# Function to create a directory if it does not exist
function create_directory {
    if [ ! -d "$1" ]; then
        mkdir -p "$1" || error_exit "Failed to create directory $1."
    fi
}

# Function to make a file executable
function make_executable {
    chmod +x "$1" || error_exit "Failed to make file $1 executable."
}

# Function to download the oui.txt file
function download_oui {
    echo "Downloading the oui.txt file..."
    wget -O "$OUI_FILE_PATH" http://standards-oui.ieee.org/oui/oui.txt || error_exit "Failed to download the oui.txt file."
}

# Determine the home directory
HOME_DIR=$(eval echo ~$USER)

# Gather user inputs
directory="$HOME_DIR/blueberry"
LOCAL_BIN="$HOME_DIR/.local/bin"

[ -d "$directory" ] && {
    echo -e "Previous installation detected at $directory."
    read -p "Would you like to proceed with reinstalling? (y/n): " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && error_exit "Installation aborted."
    echo "Deleting the existing directory and reinstalling..."
    rm -rf "$directory"
    echo "Previous installation removed."
}

while true; do
    read -p "Do you have a macvendors API token? (y/n): " -n 1 -r response
    echo
    case $response in
        [Yy])
            read -p "Enter your macvendors API token: " macvendors_api_token
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
}
# Update package list and upgrade packages
sudo apt-get update
sudo apt-get upgrade -y

# Check if Python3, pip, and wget are installed or install them
check_or_install_command python3
check_or_install_command python3-pip
check_or_install_command wget

# Create the directory
create_directory "$directory"

# Clone the GitHub repository
cd "$directory" || error_exit "Failed to change directory to '$directory'."
git clone https://github.com/yanniedog/blueberry.git . || error_exit "Failed to clone the repository."

# Generate a unique 6-character code
serial=$(cat /proc/cpuinfo | grep Serial | cut -d ' ' -f 2)
timestamp=$(date +%s)
hash=$(echo -n "${serial}${timestamp}" | sha256sum | cut -c1-6)

# Insert the unique identifier into env.dat
echo "unique_id = '${hash}'" > env.dat

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

BLUEBERRY_DIR="$directory"
source "\$BLUEBERRY_DIR/venv/bin/activate"
python "\$BLUEBERRY_DIR/blueberry.py"
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

# Update config file with the API token
cat >"$directory/config.me" <<EOF
[DEFAULT]
CSV_FILE_PATH = $directory/detected.csv
API_TOKEN = $macvendors_api_token
OUI_FILE_PATH = $directory/oui.txt
EOF

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
