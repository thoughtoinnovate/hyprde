#!/usr/bin/env python3
import subprocess
import json
import re
import sys

def run_command(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        return result.stdout
    except Exception as e:
        return ""

def get_signal_icon(rssi):
    if not rssi: return "󰤮"
    try:
        rssi = int(rssi)
        if rssi >= -50: return "󰤨"
        if rssi >= -65: return "󰤥"
        if rssi >= -80: return "󰤢"
        if rssi >= -95: return "󰤟"
        return "󰤯"
    except: return "󰤮"

def get_battery_icon(percentage):
    if percentage is None: return ""
    try:
        p = int(percentage)
        if p >= 90: return "󰁹"
        if p >= 80: return "󰂀"
        if p >= 70: return "󰂀"
        if p >= 60: return "󰁿"
        if p >= 50: return "󰁾"
        if p >= 40: return "󰁽"
        if p >= 30: return "󰁼"
        if p >= 20: return "󰁻"
        if p >= 10: return "󰁺"
        return "󰂎"
    except: return ""

def get_device_info(mac):
    info_raw = run_command(f"bluetoothctl info {mac}")
    info = {}
    alias_match = re.search(r"Alias: (.*)", info_raw)
    info['name'] = alias_match.group(1) if alias_match else "Unknown"
    info['connected'] = "Connected: yes" in info_raw
    battery_match = re.search(r"Battery Percentage: .*\((.*)\)", info_raw)
    info['battery'] = int(battery_match.group(1)) if battery_match else None
    info['battery_icon'] = get_battery_icon(info['battery'])
    icon_match = re.search(r"Icon: (.*)", info_raw)
    icon_type = icon_match.group(1) if icon_match else ""
    if "audio" in icon_type or "headset" in icon_type: info['icon'] = "󰋋"
    elif "keyboard" in icon_type: info['icon'] = "󰌌"
    elif "mouse" in icon_type: info['icon'] = "󰍽"
    else: info['icon'] = "󰂯"
    rssi_match = re.search(r"RSSI: (-\d+)", info_raw)
    info['rssi'] = rssi_match.group(1) if rssi_match else None
    info['signal_icon'] = get_signal_icon(info['rssi'])
    info['mac'] = mac
    return info

def main():
    # Global Power Status
    show_raw = run_command("bluetoothctl show")
    powered = "Powered: yes" in show_raw
    
    devices_raw = run_command("bluetoothctl devices")
    device_list = []
    if devices_raw:
        for line in devices_raw.strip().split('\n'):
            match = re.search(r"Device ([0-9A-F:]+) (.*)", line)
            if match:
                device_list.append(get_device_info(match.group(1)))
    
    device_list.sort(key=lambda x: (not x['connected'], x['name']))
    
    output = {
        "powered": powered,
        "devices": device_list
    }
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()