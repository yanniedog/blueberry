#!/usr/bin/env python3

import csv
import os
import re
import subprocess
import requests
from datetime import datetime
import time
from colorama import Fore, Style, init

init(autoreset=True)

CSV_FILE_PATH = '/home/pi/bt.csv'

def color_rssi(value):
    if not value:  # Add this line to check for empty strings
        return ''
    value = int(value)
    if value > -60:
        return Fore.GREEN + str(value) + Style.RESET_ALL
    elif value > -70:
        return Fore.YELLOW + str(value) + Style.RESET_ALL
    else:
        return Fore.RED + str(value) + Style.RESET_ALL

def parse_btmgmt_output_line(line):
    """Parse a line from btmgmt output and return a dictionary with additional information."""
    additional_info = {}
    name_match = re.search(r"name (.+)", line)
    if name_match:
        additional_info['name'] = name_match.group(1)
    return additional_info

def get_oui_info(mac_address):
    """Get the OUI information for the given MAC address."""
    oui = mac_address[:8].replace(':', '-').upper()
    url = f"https://api.macvendors.com/{oui}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            return ''
    except requests.exceptions.RequestException:
        return ''

def process_btmgmt_output():
    """Process the output of the btmgmt command and return a dictionary of found devices."""
    found_devices = {}
    process = subprocess.Popen(['btmgmt', 'find'], stdout=subprocess.PIPE, text=True)
    additional_info = {}
    try:
        for line in process.stdout:
            additional_info = parse_btmgmt_output_line(line)
            if "dev_found" in line:
                mac_address_match = re.search(r": ([\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2}:[\dA-F]{2})", line)
                rssi_match = re.search(r"rssi (-\d+)", line)
                if mac_address_match and rssi_match:
                    mac_address = mac_address_match.group(1)
                    rssi = rssi_match.group(1)
                    if mac_address not in found_devices:
                        oui_info = get_oui_info(mac_address)
                        if 'Organization' in oui_info:
                            manufacturer = oui_info.split('\n')[1].split(': ')[1]
                        else:
                            manufacturer = ''
                    else:
                        manufacturer = found_devices[mac_address].get('Manufacturer', '')
                    name = additional_info.get('name', found_devices.get(mac_address, {}).get('Name', ''))
                    found_devices[mac_address] = {'MAC': mac_address, 'RSSI': rssi, 'Name': name, 'Manufacturer': manufacturer}
    finally:
        process.stdout.close()
        process.wait()
    update_csv(found_devices)

def create_csv_file():
    """Create a new CSV file with the appropriate header."""
    with open(CSV_FILE_PATH, 'w', newline='') as csvfile:
        fieldnames = ['MAC', 'Name', 'Manufacturer', 'RSSI', 'Min RSSI', 'Avg RSSI', 'Max RSSI', 'Last Seen']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

def read_csv_file():
    """Read the CSV file and return its contents as a list of dictionaries."""
    with open(CSV_FILE_PATH, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        rows = [row for row in reader]
    return rows

def write_csv_file(updated_rows):
    """Write the updated rows to the CSV file."""
    with open(CSV_FILE_PATH, 'w', newline='') as csvfile:
        fieldnames = ['MAC', 'Name', 'Manufacturer', 'RSSI', 'Min RSSI', 'Avg RSSI', 'Max RSSI', 'Last Seen']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in updated_rows:
            writer.writerow(row)

def update_csv(found_devices):
    """Update the CSV file with the new devices found."""
    if not os.path.exists(CSV_FILE_PATH):
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
            avg_rssi = (int(row.get('Avg RSSI', rssi)) + rssi) // 2  # Updated line
            last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            updated_row = {'MAC': mac, 'Name': device['Name'], 'Manufacturer': device['Manufacturer'],
                           'RSSI': rssi, 'Min RSSI': min_rssi, 'Avg RSSI': avg_rssi, 'Max RSSI': max_rssi, 'Last Seen': last_seen}
            updated_rows.append(updated_row)
            del found_devices[mac]
        else:
            updated_rows.append(row)

    for mac, device in found_devices.items():
        rssi = int(device['RSSI'])
        last_seen = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_row = {'MAC': mac, 'Name': device['Name'], 'Manufacturer': device['Manufacturer'],
                   'RSSI': rssi, 'Min RSSI': rssi, 'Avg RSSI': rssi, 'Max RSSI': rssi, 'Last Seen': last_seen}
        updated_rows.append(new_row)

    write_csv_file(updated_rows)

def read_and_display_csv():
    if os.path.exists(CSV_FILE_PATH) and os.path.getsize(CSV_FILE_PATH) > 0:
        with open(CSV_FILE_PATH, mode='r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            print(f"{'Last Seen':<20}{'MAC':<20}{'RSSI':<10}{'Min':<10}{'Avg':<10}{'Max':<10}{'Name':<20}{'Manufacturer':<50}")
            for row in reader:
                last_seen = row.get('Last Seen', '')
                mac = row.get('MAC', '')
                rssi = color_rssi(row.get('RSSI', '0'))
                min_rssi = color_rssi(row.get('Min RSSI', '0'))
                avg_rssi = color_rssi(row.get('Avg RSSI', '0'))
                max_rssi = color_rssi(row.get('Max RSSI', '0'))
                name = row.get('Name', '')
                manufacturer = row.get('Manufacturer', '')
                print(f"{last_seen:<20}{mac:<20}{rssi:<10}{min_rssi:<10}{avg_rssi:<10}{max_rssi:<10}{name:<20}{manufacturer:<50}")
    else:
        print("No data found in the CSV file.")

if __name__ == "__main__":
    while True:
        process_btmgmt_output()
        read_and_display_csv()
        time.sleep(10)