#!/usr/bin/env python3
import json
import subprocess
import os
import re

# Paths
SCRIPT_DIR = os.path.expanduser("~/.config/hypr/scripts")
GEN_CONFIG_PATH = "/tmp/waybar_bt_gen.json"

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return result.stdout
    except:
        return ""

def get_devices():
    devices_raw = run_command("bluetoothctl devices")
    device_list = []
    if devices_raw:
        lines = devices_raw.strip().split('\n')
        for line in lines:
            match = re.search(r"Device ([0-9A-F:]+) (.*)", line)
            if match:
                mac = match.group(1)
                info = run_command(f"bluetoothctl info {mac}")
                connected = "Connected: yes" in info
                
                # Icons
                icon = "󰂯"
                if "audio" in info or "headset" in info: icon = "󰋋"
                elif "keyboard" in info: icon = "󰌌"
                elif "mouse" in info: icon = "󰍽"
                
                # Battery
                batt_match = re.search(r"Battery Percentage: .*\((.*)\)", info)
                batt = f"{batt_match.group(1)}%" if batt_match else ""
                
                device_list.append({
                    "mac": mac,
                    "name": match.group(2)[:18],
                    "connected": connected,
                    "icon": icon,
                    "battery": batt
                })
    return device_list

def generate_config():
    devices = get_devices()
    modules_list = ["custom/bt-header"]
    
    config = {
        "id": "bluetooth-center",
        "layer": "overlay",
        "exclusive": False,
        "passthrough": False,
        "position": "top",
        "margin": "22px 15px 0px 0px",
        "spacing": 8,
        "modules-right": ["group/bt_panel"],
        "group/bt_panel": {
            "orientation": "vertical",
            "modules": modules_list
        },
        "custom/bt-header": {
            "format": "󰂯 Bluetooth Center",
            "on-click": f"{SCRIPT_DIR}/bluetooth.sh toggle",
            "exec": f"{SCRIPT_DIR}/bluetooth.sh status",
            "return-type": "json",
            "interval": 2
        }
    }

    connected = [d for d in devices if d['connected']]
    paired = [d for d in devices if not d['connected']]

    # Connected Section
    if connected:
        config["custom/title-conn"] = {"format": "<span>CONNECTED</span>", "tooltip": False}
        modules_list.append("custom/title-conn")
        for i, dev in enumerate(connected):
            mod_name = f"custom/dev-conn-{i}"
            modules_list.append(mod_name)
            batt = f" {dev['battery']}" if dev['battery'] else ""
            config[mod_name] = {
                "format": f"{dev['icon']}  {dev['name']}{batt}  󰄬",
                "on-click": f"{SCRIPT_DIR}/bluetooth_device_toggle.sh {dev['mac']} toggle",
                "class": "enbld"
            }

    # Paired Section
    if paired:
        config["custom/title-pair"] = {"format": "<span>PAIRED</span>", "tooltip": False}
        modules_list.append("custom/title-pair")
        for i, dev in enumerate(paired):
            mod_name = f"custom/dev-pair-{i}"
            modules_list.append(mod_name)
            config[mod_name] = {
                "format": f"{dev['icon']}  {dev['name']}",
                "on-click": f"{SCRIPT_DIR}/bluetooth_device_toggle.sh {dev['mac']} toggle",
                "class": "disbld"
            }

    modules_list.append("custom/bt-footer")
    config["custom/bt-footer"] = {
        "format": "Advanced Settings 󰒓",
        "on-click": "blueman-manager"
    }

    with open(GEN_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

if __name__ == "__main__":
    generate_config()