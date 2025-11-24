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
               sudo pacman -S --noconfirm --needed $package
                ;;
            debian)
                sudo apt install -y --no-install-recommends $package
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
# Usage: backup_if_exists <target_path> <backup_base_dir>
backup_if_exists() {
    local target="$1"
    local backup_base_dir="$2"
    
    if [ -e "$target" ]; then
        # Get the parent directory and basename of target
        local target_parent=$(dirname "$target")
        local target_name=$(basename "$target")
        
        # Create parent directory structure in backup if needed
        local backup_target_parent="$backup_base_dir$target_parent"
        mkdir -p "$backup_target_parent"
        
        # Move existing file/directory to backup
        echo "Backing up existing: $target -> $backup_target_parent/$target_name"
        mv "$target" "$backup_target_parent/$target_name"
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

# Create timestamped backup directory
BACKUP_DIR="$HOME/.config/hyprde_backup_$(date +%Y%m%d_%H%M%S)"
echo "Copying config Files ......"

# Backup and copy config files
backup_if_exists "$HOME/.config/alacritty" "$BACKUP_DIR"
cp -rf ./configs/alacritty $HOME/.config

backup_if_exists "$HOME/.config/hypr" "$BACKUP_DIR"
cp -rf ./configs/hypr $HOME/.config

backup_if_exists "$HOME/.config/mako" "$BACKUP_DIR"
cp -rf ./configs/mako $HOME/.config

backup_if_exists "$HOME/.config/waybar" "$BACKUP_DIR"
cp -rf ./configs/waybar $HOME/.config

backup_if_exists "$HOME/.config/wofi" "$BACKUP_DIR"
cp -rf ./configs/wofi $HOME/.config

backup_if_exists "$HOME/.config/mimeapps.list" "$BACKUP_DIR"
cp ./configs/mimeapps.list $HOME/.config/

# Update desktop database
update-desktop-database

# Set default MIME associations
xdg-mime default org.pwmt.zathura.desktop application/pdf
xdg-mime default imv.desktop image/png image/jpeg image/gif image/bmp image/tiff image/webp
xdg-mime default mpv.desktop video/mp4 video/avi video/mkv video/webm audio/mp3 audio/flac audio/wav

echo "Copying desktop entries..."
mkdir -p $HOME/.local/share/applications

# Backup existing desktop entries if they exist
for app_file in ./configs/applications/*; do
    if [ -f "$app_file" ]; then
        app_name=$(basename "$app_file")
        backup_if_exists "$HOME/.local/share/applications/$app_name" "$BACKUP_DIR"
    fi
done
cp -rf ./configs/applications/* $HOME/.local/share/applications/

echo "Creating dedicated session menu directory..."
mkdir -p $HOME/.local/share/hyprocket-session/applications

# Backup existing session menu entries if they exist
for app_file in ./configs/applications/*; do
    if [ -f "$app_file" ]; then
        app_name=$(basename "$app_file")
        backup_if_exists "$HOME/.local/share/hyprocket-session/applications/$app_name" "$BACKUP_DIR"
    fi
done
cp -rf ./configs/applications/* $HOME/.local/share/hyprocket-session/applications/

echo "Making scripts executable..."
chmod +x $HOME/.config/hypr/scripts/*.sh
chmod +x $HOME/.config/hypr/scripts/gammastep/*.sh


echo "Creating wallpaper directories."
mkdir -p $HOME/Pictures/wallpapers/sunrise
mkdir -p $HOME/Pictures/wallpapers/sunset

# Inform user about backup location if any files were backed up
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
    echo ""
    echo "Existing config files backed up to: $BACKUP_DIR"
    echo ""
fi

echo "You are ready to go.."