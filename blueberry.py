import csv
import os
import re
import subprocess
import requests
from datetime import datetime
import time
from colorama import Fore, Style, init

init(autoreset=True)
CSV_FILE_PATH = '~/blueberry/detected.csv'
API_TOKEN = "your_api_token_here"

def color_rssi(value):
    if not value:
        return ''
    value = int(value)
    if value > -60:
        return Fore.GREEN + str(value) + Style.RESET_ALL
    elif value > -70:
        return Fore.YELLOW + str(value) + Style.RESET_ALL
    else:
        return Fore.RED + str(value) + Style.RESET_ALL

def parse_btmgmt_output_line(line):
    additional_info = {}
    name_match = re.search(r"name (.+)", line)
    if name_match:
        additional_info['name'] = name_match.group(1)
    return additional_info

def get_oui_info(mac_address):
    api_token = API_TOKEN
    mac_address_formatted = mac_address.replace(':', '').upper()
    url = f"https://api.macvendors.com/v1/lookup/{mac_address_formatted}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            json_response = response.json()
            return json_response['data']
        else:
            return {'organization_name': '', 'assignment': '', 'organization_address': '', 'registry': ''}
    except requests.exceptions.RequestException:
        return {'organization_name': '', 'assignment': '', 'organization_address': '', 'registry': ''}

def process_btmgmt_output():
    found_devices = {}
    process = subprocess.Popen(['sudo', 'btmgmt', 'find'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    additional_info = {}
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
                    if mac_address not in found_devices:
                        oui_data = get_oui_info(mac_address)
                        time.sleep(0.5)  # To handle the API rate limit
                    else:
                        oui_data = found_devices[mac_address].get('OUI_Data', {'organization_name': '', 'assignment': '', 'organization_address': '', 'registry': ''})
                    name = additional_info.get('name', found_devices.get(mac_address, {}).get('Name', ''))
                    found_devices[mac_address] = {'MAC': mac_address, 'RSSI': rssi, 'Name': name, 'OUI_Data': oui_data}
    finally:
        process.stdout.close()
        process.wait()
    update_csv(found_devices)

def create_csv_file():
    with open(os.path.expanduser(CSV_FILE_PATH), 'w', newline='') as csvfile:
        fieldnames = ['Last Seen', 'MAC', 'RSSI', 'Min RSSI', 'Avg RSSI', 'Max RSSI', 'Name', 'Manufacturer', 'Assignment', 'Organization Address', 'Registry']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def read_csv_file():
    with open(os.path.expanduser(CSV_FILE_PATH), 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader]
    return rows

def write_csv_file(updated_rows):
    with open(os.path.expanduser(CSV_FILE_PATH), 'w', newline='') as csvfile:
        fieldnames = ['Last Seen', 'MAC', 'RSSI', 'Min RSSI', 'Avg RSSI', 'Max RSSI', 'Name', 'Manufacturer', 'Assignment', 'Organization Address', 'Registry']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in updated_rows:
            writer.writerow(row)

def update_csv(found_devices):
    if not os.path.exists(os.path.expanduser(CSV_FILE_PATH)):
        create_csv_file()

    rows = read_csv_file()
    updated_rows = []

    for row in rows:
        mac = row['MAC']
        if mac in found_devices:
            device = found_devices[mac]
            rssi = int(device['RSSI'])
            min_rssi = min(int(row.get('Min RSSI', rssi)), rssi)
            max_rssi = max(int(row.get('Max RSSI', rssi)), rssi)
            avg_rssi = (int(row.get('Avg RSSI', rssi)) + rssi) // 2
            last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            oui_data = device['OUI_Data']
            updated_row = {'Last Seen': last_seen, 'MAC': mac, 'RSSI': rssi, 'Min RSSI': min_rssi, 'Avg RSSI': avg_rssi, 'Max RSSI': max_rssi, 'Name': device['Name'],
                           'Manufacturer': oui_data['organization_name'], 'Assignment': oui_data['assignment'], 'Organization Address': oui_data['organization_address'], 'Registry': oui_data['registry']}
            updated_rows.append(updated_row)
            del found_devices[mac]
        else:
            updated_rows.append(row)

    for mac, device in found_devices.items():
        rssi = int(device['RSSI'])
        last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        oui_data = device['OUI_Data']
        new_row = {'Last Seen': last_seen, 'MAC': mac, 'RSSI': rssi, 'Min RSSI': rssi, 'Avg RSSI': rssi, 'Max RSSI': rssi, 'Name': device['Name'],
                   'Manufacturer': oui_data['organization_name'], 'Assignment': oui_data['assignment'], 'Organization Address': oui_data['organization_address'], 'Registry': oui_data['registry']}
        updated_rows.append(new_row)

    updated_rows.sort(key=lambda x: x['Last Seen'], reverse=True)
    write_csv_file(updated_rows)

def read_and_display_csv():
    if os.path.exists(os.path.expanduser(CSV_FILE_PATH)) and os.path.getsize(os.path.expanduser(CSV_FILE_PATH)) > 0:
        with open(os.path.expanduser(CSV_FILE_PATH), mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"{'Last Seen':<20} {'MAC':<20} {'RSSI':<7} {'Min':<7} {'Avg':<7} {'Max':<7} {'Name':<20} {'Manufacturer':<30} {'Assignment':<12} {'Organization Address':<30} {'Registry':<10}")
            for row in reader:
                last_seen = row.get('Last Seen', '')
                mac = row.get('MAC', '')
                rssi = color_rssi(row.get('RSSI', '0'))
                min_rssi = color_rssi(row.get('Min RSSI', '0'))
                avg_rssi = color_rssi(row.get('Avg RSSI', '0'))
                max_rssi = color_rssi(row.get('Max RSSI', '0'))
                name = row.get('Name', '')
                manufacturer = row.get('Manufacturer', '')
                assignment = row.get('Assignment', '')
                organization_address = row.get('Organization Address', '')
                registry = row.get('Registry', '')
                print(f"{last_seen:<20} {mac:<20} {rssi:<7} {min_rssi:<7} {avg_rssi:<7} {max_rssi:<7} {name:<20} {manufacturer:<30} {assignment:<12} {organization_address:<30} {registry:<10}")
    else:
        print("No data found in the CSV file.")

if __name__ == "__main__":
    while True:
        process_btmgmt_output()
        read_and_display_csv()
        time.sleep(10)
