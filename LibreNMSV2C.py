import os
import csv
import requests
import datetime
from tqdm import tqdm
from itertools import count
from time import sleep

# ================
# Configuration
# ================
LIBRENMS_URL = "https://your-librenms-instance.example.com"
API_TOKEN = "your_api_token_here"
PAGE_SIZE = 100

# ================
# Paths
# ================
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
base_path = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(base_path, f"librenms_snmpv2_devices_{timestamp}.csv")
log_path = os.path.join(base_path, f"librenms_export_log_{timestamp}.txt")

# ================
# Logging
# ================
def write_log(message, level="INFO"):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {message}"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

# ================
# HTTP Headers
# ================
headers = {
    "X-Auth-Token": API_TOKEN,
    "Accept": "application/json"
}

# ================
# API Helpers
# ================
def get_devices_page(page):
    url = f"{LIBRENMS_URL}/api/v0/devices?limit={PAGE_SIZE}&page={page}"
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json().get("devices", [])
    except Exception as e:
        write_log(f"Error fetching page {page}: {e}", "ERROR")
        return []

def extract_group(device):
    if isinstance(device.get("group"), str):
        return device["group"]
    elif isinstance(device.get("groups"), list) and len(device["groups"]) > 0:
        group_entry = device["groups"][0]
        if isinstance(group_entry, dict):
            return group_entry.get("name", "") or str(group_entry)
        else:
            return str(group_entry)
    return ""

# ================
# Startup
# ================
write_log("Export started")
write_log(f"Output path: {base_path}")

# Create CSV file
with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Hostname", "IP", "SNMP_Version", "Community", "OS", "Group", "Location"])

total_exported = 0
seen_device_ids = set()

write_log("Starting dynamic pagination...")

# ================
# Device Loop
# ================
for page in tqdm(count(1), desc="Fetching devices", unit="page"):
    devices = get_devices_page(page)
    if not devices:
        write_log(f"No more devices on page {page}. Stopping.")
        break

    rows = []
    new_ids = 0

    for d in devices:
        device_id = d.get("device_id")
        if not device_id or device_id in seen_device_ids:
            continue  # Already seen

        seen_device_ids.add(device_id)

        if d.get("snmpver") != "v2c":
            continue  # Skip non-v2c

        hostname = d.get("hostname", "")
        ip = d.get("ip", "")
        snmpver = d.get("snmpver", "")
        community = d.get("community", "")
        os_name = d.get("os", "")
        location = d.get("location", "")
        group = extract_group(d)

        row = [hostname, ip, snmpver, community, os_name, group, location]
        rows.append(row)
        new_ids += 1

    if rows:
        with open(csv_path, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(rows)

        total_exported += len(rows)
        write_log(f"Page {page}: {new_ids} new SNMPv2c devices exported (total: {total_exported})")

    if new_ids == 0:
        write_log(f"No new devices found on page {page}. Stopping.")
        break

    sleep(0.1)  # Gentle API throttling

# ================
# Finish
# ================
write_log(f"✅ Export complete. Total devices exported: {total_exported}")
print("\n✅ Export complete.")
print(f"📄 CSV file saved: {csv_path}")
print(f"📝 Log file saved: {log_path}")
