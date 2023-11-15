# Blueberry: Bluetooth Scanner for Raspberry Pi

## Overview
Blueberry is a tool for tracking Bluetooth devices using a Raspberry Pi. It scans for devices, logs their signal strength (RSSI), and other details, then saves the data to a CSV file for later analysis.

## Prerequisites
- Raspberry Pi with Raspbian OS (Bookworm)
- Python 3.x
- Git
- pip
- Internet connection

## Installation
To install Blueberry, run the following command in your terminal:

```sh
bash <(curl -s https://raw.githubusercontent.com/yanniedog/blueberry/setup.sh)
```

This command downloads and executes the setup script, which will:
- Check for Python3 and pip
- Create a `blueberry` directory in the home folder
- Clone the Blueberry repository into this directory
- Create a Python virtual environment and activate it
- Install the required Python packages
- Deactivate the virtual environment and finalize the setup

## Usage
After installation, navigate to the `blueberry` directory:

```sh
cd /home/pi/blueberry
```

Then, start the Bluetooth tracking by running the `blueberry.py` script:

```sh
source venv/bin/activate
python blueberry.py
```

The script will continuously scan for nearby Bluetooth devices and output the results to the console and the `bt.csv` file in the same directory.

## Output
The `bt.csv` file will contain the following columns:

- MAC: The MAC address of the detected Bluetooth device
- Name: The name of the Bluetooth device
- Manufacturer: The manufacturer of the device obtained via OUI lookup
- RSSI: The Received Signal Strength Indicator (RSSI) value for the device
- Min RSSI: The minimum RSSI recorded for the device
- Avg RSSI: The average RSSI calculated over the period of detection
- Max RSSI: The maximum RSSI recorded for the device
- Last Seen: The last timestamp when the device was detected

## Note
Ensure that the Bluetooth interface on the Raspberry Pi is enabled and not blocked by any other services before running the script.

---

For more information, refer to the comments in the `blueberry.py` script. Happy tracking!
