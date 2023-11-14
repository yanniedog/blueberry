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

config = configparser.ConfigParser()
config_file_path = 'config.me'
print(f"Reading configuration from {config_file_path}")
config.read(config_file_path)
unrecognized_mac_cache = set()  # Initialize the cache for unrecognized MAC addresses

CSV_FILE_PATH = config.get('DEFAULT', 'CSV_FILE_PATH', fallback='~/blueberry/detected.csv')
API_TOKEN = config.get('DEFAULT', 'API_TOKEN', fallback='your_api_token_here')
OUI_FILE_PATH = config.get('DEFAULT', 'OUI_FILE_PATH', fallback='~/blueberry/oui.txt')
SORT_COLUMN_NUMBER = int(config.get('DEFAULT', 'sort_column_number', fallback='1')) - 1 # Subtract 1 to make it 0-indexed
SORT_ORDER = config.get('DEFAULT', 'sort_order', fallback='ascending')
SORT_KEY = config.get('DEFAULT', 'sort_key', fallback='RSSI')  # Fallback to 'RSSI' if not specified

init(autoreset=True)

oui_cache = {}
oui_data = {}
with open(os.path.expanduser(OUI_FILE_PATH), 'r') as file:
    for line in file:
        if "(base 16)" in line:
            parts = line.split('\t')
            mac_prefix = parts[0].strip().replace('-', '').upper()
            company_name = parts[1].strip()
            oui_data[mac_prefix] = company_name

def color_rssi(value, colorize=True):
    if not value:
        return ''
    value = int(float(value))
    if not colorize:
        return Fore.LIGHTBLACK_EX + str(value) + Style.RESET_ALL
    if value >= -60:
        return Fore.GREEN + str(value) + Style.RESET_ALL
    elif value >= -70:
        return Fore.YELLOW + str(value) + Style.RESET_ALL
    else:
        return Fore.RED + str(value) + Style.RESET_ALL

def parse_btmgmt_output_line(line, current_mac_address, found_devices):
    name_match = re.search(r"name\s(.+)$", line.strip())
    if name_match and current_mac_address and current_mac_address in found_devices:
        name = name_match.group(1).strip()
        print(f"Found name: {name} for MAC address: {current_mac_address}")
        found_devices[current_mac_address]['Name'] = name
        return {'name': name}
    else:
        return {}


def get_oui_info_from_file(mac_address):
    mac_prefix = mac_address.replace(':', '')[:6].upper()
    return oui_data.get(mac_prefix)

last_api_request_time = 0
api_usage = {'count': 0, 'reset_time': datetime.now()}
total_loops = 0

def check_api_request_limit():
    global api_usage
    current_time = datetime.now()
    if current_time > api_usage['reset_time']:
        api_usage = {'count': 0, 'reset_time': current_time + timedelta(days=1)}
    return api_usage['count'] < 1000

def increment_api_usage():
    global api_usage
    api_usage['count'] += 1

def get_oui_info(mac_address):
    global last_api_request_time, api_usage, unrecognized_mac_cache, oui_cache

    # Check cache first
    if mac_address in oui_cache:
        return oui_cache[mac_address]

    if mac_address in unrecognized_mac_cache:
        return None

    if not check_api_request_limit():
        print("API request limit reached")
        return None

    current_time = time.time()
    time_since_last_request = current_time - last_api_request_time
    # if time_since_last_request < 10:  # Increase delay to 10 seconds
    #     time.sleep(10 - time_since_last_request)

    url = f"https://api.macvendors.com/{mac_address}"
    try:
        response = requests.get(url)
        last_api_request_time = time.time()
        increment_api_usage()

        if response.status_code == 200:
            # Add successful response to cache
            oui_cache[mac_address] = response.text.strip()
            return response.text.strip()
        elif response.status_code == 404:
            unrecognized_mac_cache.add(mac_address)
            print(f"MAC address {mac_address} not found in API.")
            return None
        else:
            print(f"API request failed with status code {response.status_code}, Response: {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

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
            print(f"Updating existing row for MAC {mac} with name {device['Name']}")
            existing_row.update({
                'First Seen': first_seen,
                'Last Seen': last_seen,
                'MAC': mac,
                'RSSI': rssi,
                'Min RSSI': min_rssi,
                'Mean RSSI': mean_rssi,
                'Max RSSI': max_rssi,
                'sd': sd,
                'Dur': dur,
                'Manufacturer': manufacturer_info,
                'rssi_list': ','.join(map(str, rssi_list)),
                'Name': device['Name'] if device['Name'] else existing_row.get('Name', ''),
                'Seen Count': int(existing_row.get('Seen Count', '0')) + 1
            })
            updated_rows.append(existing_row)
        else:
            first_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"Adding new row for MAC {mac} with name {device['Name']}")
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
                'rssi_list': device['RSSI'],
                'Name': device['Name'],
                'Seen Count': 1
            }
            updated_rows.append(new_row)

    updated_rows.extend([item for item in existing_data if item['MAC'] not in found_devices])
    write_csv_file(updated_rows)

def create_csv_file():
    with open(os.path.expanduser(CSV_FILE_PATH), 'w', newline='') as csvfile:
        fieldnames = ['Last Seen', 'First Seen', 'MAC', 'Name', 'RSSI', 'Min RSSI', 'Mean RSSI', 'Max RSSI', 'sd', 'Dur', 'Manufacturer', 'rssi_list', 'Seen Count']
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
        fieldnames = ['Last Seen', 'First Seen', 'MAC', 'Name', 'RSSI', 'Min RSSI', 'Mean RSSI', 'Max RSSI', 'sd', 'Dur', 'Manufacturer', 'rssi_list', 'Seen Count']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted(rows, key=lambda x: int(float(x['RSSI'])), reverse=True):
            writer.writerow(row)

def process_btmgmt_output():
    global total_loops, oui_cache
    api_call_made = False
    print("Starting process_btmgmt_output")
    found_devices = {}
    process = subprocess.Popen(['sudo', 'btmgmt', 'find'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    current_mac_address = None
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            if "dev_found" in line:
                mac_address_match = re.search(r": ([\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2})", line)
                if mac_address_match:
                    current_mac_address = mac_address_match.group(1)
                    if not api_call_made and current_mac_address not in oui_cache:
                        oui_info = get_oui_info(current_mac_address)
                        if oui_info is not None:
                            api_call_made = True
                        found_devices[current_mac_address] = {
                            'MAC': current_mac_address,
                            'RSSI': '',
                            'OUI_Info': oui_info,
                            'Name': ''
                        }
            additional_info = parse_btmgmt_output_line(line, current_mac_address, found_devices)
            if "dev_found" in line and current_mac_address in found_devices:
                rssi_match = re.search(r"rssi (-\d+)", line)
                if rssi_match:
                    rssi = rssi_match.group(1)
                    found_devices[current_mac_address]['RSSI'] = rssi

    finally:
        process.stdout.close()
        process.wait()
    update_csv(found_devices)
    print("Ending process_btmgmt_output")



def read_and_display_csv():
    print("Starting read_and_display_csv")
    if os.path.exists(os.path.expanduser(CSV_FILE_PATH)) and os.path.getsize(os.path.expanduser(CSV_FILE_PATH)) > 0:
        with open(os.path.expanduser(CSV_FILE_PATH), mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"{'Last Seen':<20} {'First Seen':<20} {'MAC':<18} {'% seen':<8} {'RSSI':<7} {'Min':<7} {'Mean':<7} {'Max':<7} {'sd':<7} {'Dur':<10} {'Manufacturer':<30}")

            rows = [row for row in reader]
            rows.sort(key=lambda x: x.get(SORT_KEY, ""), reverse=(SORT_ORDER == 'descending'))

            if rows:  # Check if rows is not empty
                for row in rows:
                    last_seen = row.get('Last Seen', '').ljust(20)
                    first_seen = row.get('First Seen', '').ljust(20)
                    mac = row.get('MAC', '').ljust(18) # determines gap between MAC and % seen (18 is a good number)
                    name = row.get('Name', '').ljust(0)
                    rssi = row.get('RSSI', '0')
                    min_rssi = row.get('Min RSSI', '0')
                    mean_rssi = row.get('Mean RSSI', '0')
                    max_rssi = row.get('Max RSSI', '0')
                    sd = row.get('sd', '0').ljust(7) # determines the gap between sd and Dur
                    dur = row.get('Dur', '00:00:00').ljust(10) 
                    manufacturer = row.get('Manufacturer', '').ljust(0) # determines the gap between RSSI and Min. 0 is a good number
                    seen_count = row.get('Seen Count', '0')

                    colorize = (datetime.now() - datetime.strptime(last_seen.strip(), '%Y-%m-%d %H:%M:%S')).total_seconds() < 10

                    rssi_padded = color_rssi(rssi, colorize).ljust(16)  # determines the gap between RSSI and Min. 10 is a good number
                    min_rssi_padded = color_rssi(min_rssi, colorize).ljust(16) # determines the gap between Min and Avg RSSI. 13 is a good number
                    mean_rssi_padded = color_rssi(mean_rssi, colorize).ljust(16)
                    max_rssi_padded = color_rssi(max_rssi, colorize).ljust(16)
                    sd_padded = (Fore.LIGHTBLACK_EX if not colorize else '') + sd.ljust(7) + Style.RESET_ALL
                    dur_padded = (Fore.LIGHTBLACK_EX if not colorize else '') + dur.ljust(10) + Style.RESET_ALL
                    manufacturer_padded = (Fore.LIGHTBLACK_EX if not colorize else '') + manufacturer.ljust(0) + Style.RESET_ALL

                    loops = max(1, total_loops)
                    seen_percentage = (Fore.LIGHTBLACK_EX if not colorize else '') + f"{int(row.get('Seen Count', '0')) / loops * 100:.2f}%".ljust(8) + Style.RESET_ALL # determines the gap between % Seen (Name) and RSSI. 7 is a good number

                    # Concatenate Name with Manufacturer
                    manufacturer_info = row.get('Manufacturer', '')
                    if row.get('Name'):
                        manufacturer_info += f" ({row.get('Name')})"

                    print(f"{last_seen} {first_seen} {mac} {seen_percentage} {rssi_padded} {min_rssi_padded} {mean_rssi_padded} {max_rssi_padded} {sd} {dur} {manufacturer_info.ljust(30)}")
            else:
                print("No data found in the CSV file.")
    else:
        print("CSV file does not exist or is empty.")

if __name__ == "__main__":
    while True:
        print("Starting main loop iteration")
        process_btmgmt_output()

        total_loops += 1  # Increment total_loops here
        print(f"Debug - Total Loops: {total_loops}")

        read_and_display_csv()
        time.sleep(10)

