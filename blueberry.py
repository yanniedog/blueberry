import csv
import os
import re
import subprocess
import requests
import configparser
import unicodedata
from datetime import datetime, timedelta
import time
from colorama import Fore, Style, init
import statistics

# Configuration and Initialization
config = configparser.ConfigParser()
config_file_path = 'config.me'
print(f"Reading configuration from {config_file_path}")
config.read(config_file_path)

CSV_FILE_PATH = config.get('DEFAULT', 'CSV_FILE_PATH', fallback='~/blueberry/detected.csv')
API_TOKEN = config.get('DEFAULT', 'API_TOKEN', fallback='your_api_token_here')
OUI_FILE_PATH = config.get('DEFAULT', 'OUI_FILE_PATH', fallback='~/blueberry/oui.txt')

init(autoreset=True)

# Load OUI data
oui_data = {}
with open(os.path.expanduser(OUI_FILE_PATH), 'r') as file:
    for line in file:
        if "(base 16)" in line:
            parts = line.split('\t')
            mac_prefix = parts[0].strip().replace('-', '').upper()
            company_name = parts[1].strip()
            oui_data[mac_prefix] = company_name

# Helper Functions

def color_rssi(value):
    if not value:
        return ''
    value = int(float(value))  # Convert to float first, then to int
    if value >= -60:
        return Fore.GREEN + str(value) + Style.RESET_ALL
    elif value >= -70:
        return Fore.YELLOW + str(value) + Style.RESET_ALL
    else:
        return Fore.RED + str(value) + Style.RESET_ALL

def parse_btmgmt_output_line(line):
    additional_info = {}
    name_match = re.search(r"name\s(.+)$", line.strip())
    if name_match:
        additional_info['name'] = name_match.group(1).strip()
        print(f"Found name: {additional_info['name']} for line: {line}")  # Debugging print
    return additional_info

# Cache for unrecognized MAC addresses
unrecognized_mac_cache = set()

# Function to get OUI info from file
def get_oui_info_from_file(mac_address):
    mac_prefix = mac_address.replace(':', '')[:6].upper()
    return oui_data.get(mac_prefix)

# Function to get OUI info from API with retry and rate limiting
last_api_request_time = 0
api_usage = {'count': 0, 'reset_time': datetime.now()}

def check_api_request_limit():
    global api_usage  # Declare api_usage as a global variable
    current_time = datetime.now()
    if current_time > api_usage['reset_time']:
        api_usage = {'count': 0, 'reset_time': current_time + timedelta(days=1)}
    return api_usage['count'] < 1000

def increment_api_usage():
    global api_usage  # Declare api_usage as a global variable
    api_usage['count'] += 1

def get_oui_info(mac_address):
    global last_api_request_time, api_usage, unrecognized_mac_cache

    # Check if MAC address is in the unrecognized cache
    if mac_address in unrecognized_mac_cache:
        return None

    # Rate limiting check
    if not check_api_request_limit():
        print("API request limit reached")
        return None

    # Ensuring a gap of at least 1 second between API requests
    current_time = time.time()
    time_since_last_request = current_time - last_api_request_time
    if time_since_last_request < 1:
        time.sleep(1 - time_since_last_request)

    url = f"https://api.macvendors.com/{mac_address}"
    try:
        response = requests.get(url)
        last_api_request_time = time.time()  # Update the last request time to current time
        increment_api_usage()

        if response.status_code == 200:
            return response.text.strip()
        elif response.status_code == 404:
            unrecognized_mac_cache.add(mac_address)  # Add to cache
            print(f"MAC address {mac_address} not found in API.")
            return None
        else:
            print(f"API request failed with status code {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

# Function to update CSV
def update_csv(found_devices):
    if not os.path.exists(os.path.expanduser(CSV_FILE_PATH)):
        create_csv_file()

    existing_data = read_csv_file()
    updated_rows = []

    for mac, device in found_devices.items():
        manufacturer_info = device['OUI_Info'] if device['OUI_Info'] else ''
        if device['Name']:
            manufacturer_info = manufacturer_info + f" ({device['Name']})" if manufacturer_info else device['Name']

        existing_row = next((item for item in existing_data if item['MAC'] == mac), None)
        if existing_row:
            rssi = int(device['RSSI'])
            min_rssi = min(int(existing_row.get('Min RSSI', rssi)), rssi)
            max_rssi = max(int(existing_row.get('Max RSSI', rssi)), rssi)
            rssi_list = [int(rssi_value) for rssi_value in existing_row.get('rssi_list', '').split(',') if rssi_value]
            rssi_list.append(rssi)
            mean_rssi = round(sum(rssi_list) / len(rssi_list), 2)
            last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            first_seen = existing_row.get('First Seen', last_seen)
            dur = str(timedelta(seconds=(datetime.strptime(last_seen, '%Y-%m-%d %H:%M:%S') - datetime.strptime(first_seen, '%Y-%m-%d %H:%M:%S')).total_seconds())).split('.')[0]
            sd = round(statistics.stdev(rssi_list) if len(rssi_list) > 1 else 0, 2)
            existing_row.update({
                'First Seen': first_seen,
                'Last Seen': last_seen,
                'RSSI': rssi,
                'Min RSSI': min_rssi,
                'Mean RSSI': mean_rssi,
                'Max RSSI': max_rssi,
                'sd': sd,
                'Dur': dur,
                'Manufacturer': manufacturer_info,
                'rssi_list': ','.join(map(str, rssi_list))
            })
            updated_rows.append(existing_row)
        else:
            first_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_row = {
                'First Seen': first_seen,
                'Last Seen': first_seen,
                'MAC': mac,
                'RSSI': device['RSSI'],
                'Min RSSI': device['RSSI'],
                'Mean RSSI': device['RSSI'],
                'Max RSSI': device['RSSI'],
                'sd': 0,
                'Dur': '0:00:00',
                'Manufacturer': manufacturer_info,
                'rssi_list': device['RSSI']
            }
            updated_rows.append(new_row)

    updated_rows.extend([item for item in existing_data if item['MAC'] not in found_devices])
    write_csv_file(updated_rows)

# CSV file handling functions
def create_csv_file():
    with open(os.path.expanduser(CSV_FILE_PATH), 'w', newline='') as csvfile:
        fieldnames = ['First Seen', 'Last Seen', 'MAC', 'RSSI', 'Min RSSI', 'Mean RSSI', 'Max RSSI', 'sd', 'Dur', 'Manufacturer', 'rssi_list']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def read_csv_file():
    if not os.path.exists(os.path.expanduser(CSV_FILE_PATH)):
        create_csv_file()
        return []
    with open(os.path.expanduser(CSV_FILE_PATH), 'r', newline='') as csvfile:
        return list(csv.DictReader(csvfile))

def write_csv_file(rows):
    with open(os.path.expanduser(CSV_FILE_PATH), 'w', newline='') as csvfile:
        fieldnames = ['First Seen', 'Last Seen', 'MAC', 'RSSI', 'Min RSSI', 'Mean RSSI', 'Max RSSI', 'sd', 'Dur', 'Manufacturer', 'rssi_list']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

# Function to process Bluetooth management output
def process_btmgmt_output():
    found_devices = {}
    process = subprocess.Popen(['sudo', 'btmgmt', 'find'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            additional_info = parse_btmgmt_output_line(line)
            if "dev_found" in line:
                mac_address_match = re.search(r": ([\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2})", line)
                rssi_match = re.search(r"rssi (-\d+)", line)
                if mac_address_match and rssi_match:
                    mac_address = mac_address_match.group(1)
                    rssi = rssi_match.group(1)
                    oui_info = get_oui_info_from_file(mac_address)
                    if not oui_info:
                        oui_info = get_oui_info(mac_address)
                    found_devices[mac_address] = {
                        'MAC': mac_address,
                        'RSSI': rssi,
                        'OUI_Info': oui_info,
                        'Name': additional_info.get('name', '')
                    }
    finally:
        process.stdout.close()
        process.wait()
    update_csv(found_devices)

def read_and_display_csv():
    if os.path.exists(os.path.expanduser(CSV_FILE_PATH)) and os.path.getsize(os.path.expanduser(CSV_FILE_PATH)) > 0:
        with open(os.path.expanduser(CSV_FILE_PATH), mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            # Print the column headers
            print(f"{'First Seen':<20} {'Last Seen':<20} {'MAC':<20} {'RSSI':<7} {'Min':<7} {'Mean':<7} {'Max':<7} {'sd':<7} {'Dur':<10} {'Manufacturer':<30}")
            # Print each row of data
            for row in reader:
                first_seen = row.get('First Seen', '').ljust(20)
                last_seen = row.get('Last Seen', '').ljust(20)
                mac = row.get('MAC', '').ljust(20)
                rssi = row.get('RSSI', '0')
                min_rssi = row.get('Min RSSI', '0')
                mean_rssi = row.get('Mean RSSI', '0')
                max_rssi = row.get('Max RSSI', '0')
                sd = row.get('sd', '0')
                dur = row.get('Dur', '00:00:00').ljust(10)
                manufacturer = row.get('Manufacturer', '').ljust(30)

                # Apply color and calculate the length of non-printing color characters
                rssi_colored = color_rssi(rssi)
                non_printing_length_rssi = len(rssi_colored) - len(rssi)
                rssi_padded = rssi_colored.ljust(7 + non_printing_length_rssi)

                min_rssi_colored = color_rssi(min_rssi)
                non_printing_length_min_rssi = len(min_rssi_colored) - len(min_rssi)
                min_rssi_padded = min_rssi_colored.ljust(7 + non_printing_length_min_rssi)

                mean_rssi_colored = color_rssi(mean_rssi)
                non_printing_length_mean_rssi = len(mean_rssi_colored) - len(mean_rssi)
                mean_rssi_padded = mean_rssi_colored.ljust(7 + non_printing_length_mean_rssi)

                max_rssi_colored = color_rssi(max_rssi)
                non_printing_length_max_rssi = len(max_rssi_colored) - len(max_rssi)
                max_rssi_padded = max_rssi_colored.ljust(7 + non_printing_length_max_rssi)

                print(f"{first_seen} {last_seen} {mac} {rssi_padded} {min_rssi_padded} {mean_rssi_padded} {max_rssi_padded} {sd:<7} {dur} {manufacturer}")
    else:
        print("No data found in the CSV file.")

# Main Loop
if __name__ == "__main__":
    while True:
        process_btmgmt_output()
        read_and_display_csv()  # Add this line to display the table
        time.sleep(10)
