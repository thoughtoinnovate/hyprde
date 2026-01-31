#!/bin/bash



# Function to install yq using pacman
install_packages() {

    if [ "$#" -eq 0 ];then
        echo "Software package to install is missing!"
        exit 1
    fi

    local os=$(identifyOS)
    echo "Installing packages:[$@] on $os!"
    local packages=$@

    for package in $packages; do
        package=$(echo "$package"|sed 's/^"//;s/"$//')
        case "$os" in
            arch)
               sudo pacman -S --noconfirm --needed $package base-devel
                ;;
            debian)
                sudo apt install -y --no-install-recommends $package build-essential
                ;;
            *)
                echo "Unsupported distribution: $os"
                exit 1
                ;;
        esac
    done 


}

identifyOS(){
    # Check the distribution type
if [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        arch|manjaro)
            echo "arch"
            ;;
        debian|ubuntu|linuxmint)
            echo "debian"
            ;;
        *)
            echo "Unsupported distribution: $ID"
            exit 1
            ;;
    esac
else
    echo "/etc/os-release file not found. Unable to determine the distribution type."
fi
}

# Function to backup existing files/directories with timestamp
# Usage: backup_if_exists <target_path> <backup_base_dir> <user_home>
backup_if_exists() {
    local target="$1"
    local backup_base_dir="$2"
    local user_home="$3"
    
    # Check if target exists (as root we can check user files)
    if [ ! -e "$target" ]; then
        return 0
    fi
    
    # Convert absolute path to relative path from user's home
    local relative_path="${target#$user_home/}"
    
    # If path is not under user_home, try to map common paths
    if [ "$relative_path" = "$target" ]; then
        # Check if it's under /root (when running with sudo)
        if [[ "$target" == /root/* ]]; then
            # Map /root paths to user home structure
            relative_path="${target#/root/}"
        else
            # For other paths, preserve the structure but remove leading slash
            relative_path="${target#/}"
        fi
    fi
    
    # Create backup target path
    local backup_target="$backup_base_dir/$relative_path"
    
    # Create parent directory structure in backup if needed
    local backup_target_parent=$(dirname "$backup_target")
    mkdir -p "$backup_target_parent"
    
    # Ensure backup directory is writable by the user
    if [ -n "$SUDO_USER" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$backup_base_dir" 2>/dev/null || true
    fi
    
    # Move existing file/directory to backup
    echo "Backing up existing: $target -> $backup_target"
    if [ -n "$SUDO_USER" ]; then
        # Use sudo to move
        if sudo mv "$target" "$backup_target" 2>&1; then
            # Change ownership to the actual user
            sudo chown -R "$SUDO_USER:$SUDO_USER" "$backup_target" 2>/dev/null || true
            echo "Successfully backed up: $target"
        else
            local mv_error=$?
            echo "ERROR: Failed to backup $target (exit code: $mv_error)"
            # Remove empty parent directories if mv failed
            rmdir "$backup_target_parent" 2>/dev/null || true
            return 1
        fi
    else
        if mv "$target" "$backup_target" 2>&1; then
            echo "Successfully backed up: $target"
        else
            local mv_error=$?
            echo "ERROR: Failed to backup $target (exit code: $mv_error)"
            # Remove empty parent directories if mv failed
            rmdir "$backup_target_parent" 2>/dev/null || true
            return 1
        fi
    fi
}

# Prompt for root password at the start
echo "Need priviledges for installation of packages..."
sudo echo "Installation Started..."
echo "Installing Prerequisites..."
install_packages yq
# Read the YAML file and convert it to JSON
CONFIG_FILE="config.yml"
if ! JSON_CONTENT=$(yq < "$CONFIG_FILE" 2>/dev/null); then
    echo "Error: config.yml is not valid YAML"
    exit 1
fi

# Parse JSON content using jq (which is part of yq)
PKGS="gdk-pixbuf2 $(echo "$JSON_CONTENT" |jq -r '.configs[].packages[]')"
echo "Now installing $PKGS"
install_packages $PKGS

# Get actual user's home directory (in case script is run with sudo)
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
else
    USER_HOME="$HOME"
fi

# Create backup base directory and timestamped subdirectory
BACKUP_BASE_DIR="$USER_HOME/.config/hyprde_bkps"
BACKUP_DIR="$BACKUP_BASE_DIR/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Ensure backup directories are owned by the actual user if running with sudo
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$BACKUP_BASE_DIR" 2>/dev/null || true
fi

echo "Copying config Files ......"

# Backup and copy config files
backup_if_exists "$USER_HOME/.config/alacritty" "$BACKUP_DIR" "$USER_HOME"
cp -rf ./configs/alacritty $USER_HOME/.config

backup_if_exists "$USER_HOME/.config/hypr" "$BACKUP_DIR" "$USER_HOME"
cp -rf ./configs/hypr $USER_HOME/.config

# Ensure the user owns the directory before running the build script
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/hypr"
fi

echo "Generating dynamic Hyprland configuration from TOML..."
if [ -n "$SUDO_USER" ]; then
    sudo -u "$SUDO_USER" HYPR_CONFIG_DIR="$USER_HOME/.config/hypr" python3 "$USER_HOME/.config/hypr/build_config.py"
else
    HYPR_CONFIG_DIR="$USER_HOME/.config/hypr" python3 "$USER_HOME/.config/hypr/build_config.py"
fi

backup_if_exists "$USER_HOME/.config/mako" "$BACKUP_DIR" "$USER_HOME"
cp -rf ./configs/mako $USER_HOME/.config

backup_if_exists "$USER_HOME/.config/waybar" "$BACKUP_DIR" "$USER_HOME"
cp -rf ./configs/waybar $USER_HOME/.config

backup_if_exists "$USER_HOME/.config/wofi" "$BACKUP_DIR" "$USER_HOME"
cp -rf ./configs/wofi $USER_HOME/.config

backup_if_exists "$USER_HOME/.config/mimeapps.list" "$BACKUP_DIR" "$USER_HOME"
cp ./configs/mimeapps.list $USER_HOME/.config/

# Update desktop database
update-desktop-database

# Set default MIME associations
xdg-mime default org.pwmt.zathura.desktop application/pdf
xdg-mime default imv.desktop image/png image/jpeg image/gif image/bmp image/tiff image/webp
xdg-mime default mpv.desktop video/mp4 video/avi video/mkv video/webm audio/mp3 audio/flac audio/wav

echo "Copying desktop entries..."
mkdir -p $USER_HOME/.local/share/applications

# Backup existing desktop entries if they exist
for app_file in ./configs/applications/*; do
    if [ -f "$app_file" ]; then
        app_name=$(basename "$app_file")
        backup_if_exists "$USER_HOME/.local/share/applications/$app_name" "$BACKUP_DIR" "$USER_HOME"
    fi
done
cp -rf ./configs/applications/* $USER_HOME/.local/share/applications/

echo "Creating dedicated session menu directory..."
mkdir -p $USER_HOME/.local/share/hyprocket-session/applications

# Backup existing session menu entries if they exist
for app_file in ./configs/applications/*; do
    if [ -f "$app_file" ]; then
        app_name=$(basename "$app_file")
        backup_if_exists "$USER_HOME/.local/share/hyprocket-session/applications/$app_name" "$BACKUP_DIR" "$USER_HOME"
    fi
done
cp -rf ./configs/applications/* $USER_HOME/.local/share/hyprocket-session/applications/

echo "Making scripts executable..."
chmod +x $USER_HOME/.config/hypr/scripts/*.sh
chmod +x $USER_HOME/.config/hypr/scripts/*.py
chmod +x $USER_HOME/.config/hypr/scripts/gammastep/*.sh


echo "Creating wallpaper directories."
mkdir -p $USER_HOME/Pictures/wallpapers/sunrise
mkdir -p $USER_HOME/Pictures/wallpapers/sunset

# Ensure entire backup directory is owned by the actual user if running with sudo
if [ -n "$SUDO_USER" ] && [ -d "$BACKUP_DIR" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$BACKUP_DIR" 2>/dev/null || true
fi

# Clean up empty directories in backup
if [ -d "$BACKUP_DIR" ]; then
    find "$BACKUP_DIR" -type d -empty -delete 2>/dev/null || true
fi

# Inform user about backup location if any files were backed up
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
    echo ""
    echo "Existing config files backed up to: $BACKUP_DIR"
    echo ""
elif [ -d "$BACKUP_DIR" ]; then
    # Remove backup directory if it's empty
    rmdir "$BACKUP_DIR" 2>/dev/null || true
fi

echo "You are ready to go.."