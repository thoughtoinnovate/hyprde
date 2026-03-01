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

    # Package translation layer
    if [ "$os" == "debian" ]; then
        # Map Arch-style GStreamer/recorder names to Debian names
        packages=$(echo "$packages" | sed 's/gst-libav/gstreamer1.0-libav/g')
        packages=$(echo "$packages" | sed 's/gst-plugins-ugly/gstreamer1.0-plugins-ugly/g')
        packages=$(echo "$packages" | sed 's/gst-plugins-good/gstreamer1.0-plugins-good/g')
        packages=$(echo "$packages" | sed 's/gst-plugins-bad/gstreamer1.0-plugins-bad/g')
        packages=$(echo "$packages" | sed 's/gst-plugins-base/gstreamer1.0-plugins-base/g')
        packages=$(echo "$packages" | sed 's/gpu-screen-recorder/gpu-screen-recorder/g') # Same name or needs PPA
    fi

    case "$os" in
        arch)
           sudo pacman -S --noconfirm --needed base-devel $packages
            ;;
        debian)
            sudo apt install -y --no-install-recommends build-essential $packages
            ;;
        *)
            echo "Unsupported distribution: $os"
            exit 1
            ;;
    esac

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

# Function to install Nerd Fonts (JetBrains Mono)
install_nerd_fonts() {
    local font_dir="$HOME/.local/share/fonts"
    local font_name="JetBrainsMono"
    local font_file="$font_dir/JetBrainsMonoNerdFont-Regular.ttf"

    if [ -f "$font_file" ]; then
        echo "✅ Nerd Fonts ($font_name) already installed."
        return 0
    fi

    echo "📥 Installing Nerd Fonts ($font_name)..."
    mkdir -p "$font_dir"
    
    # Use a temp dir for downloading
    local temp_dir=$(mktemp -d)
    echo "   Downloading..."
    if curl -L -o "$temp_dir/font.zip" "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/$font_name.zip"; then
        echo "   Unzipping..."
        unzip -q "$temp_dir/font.zip" -d "$temp_dir"
        mv "$temp_dir"/*.ttf "$font_dir/"
        
        echo "   Updating font cache..."
        fc-cache -f
        echo "✅ Nerd Fonts installed successfully."
    else
        echo "❌ Failed to download Nerd Fonts."
    fi
    
    rm -rf "$temp_dir"
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
PKGS="gdk-pixbuf2 python-tomlkit polkit-gnome $(echo "$JSON_CONTENT" |jq -r '.configs[].packages[]')"
echo "Now installing $PKGS"
install_packages $PKGS

# Install Nerd Fonts (Distro-agnostic)
if [ -n "$SUDO_USER" ]; then
    # Run as actual user if sudo
    sudo -u "$SUDO_USER" bash -c "$(declare -f install_nerd_fonts); install_nerd_fonts"
else
    install_nerd_fonts
fi

# Check for firejail (recommended for secure file previews)
if ! command -v firejail >/dev/null 2>&1; then
    echo ""
    echo "⚠️  WARNING: firejail is not installed"
    echo "   File previews in any_finder (SUPER+SHIFT+/) will run WITHOUT sandboxing."
    echo "   This is safe for trusted files but risky for downloaded files."
    echo "   For secure previewing of untrusted files, install with:"
    echo "     sudo pacman -S firejail"
    echo ""
fi

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
cp -rfp ./configs/alacritty $USER_HOME/.config

# Smart copy for hypr config - preserve user settings
backup_if_exists "$USER_HOME/.config/hypr" "$BACKUP_DIR" "$USER_HOME"

# Check if hyprde.toml exists and has user modifications
if [ -f "$USER_HOME/.config/hypr/hyprde.toml" ]; then
    # Calculate checksums to detect modifications
    USER_CHECKSUM=$(md5sum "$USER_HOME/.config/hypr/hyprde.toml" 2>/dev/null | cut -d' ' -f1)
    REPO_CHECKSUM=$(md5sum ./configs/hypr/hyprde.toml 2>/dev/null | cut -d' ' -f1)
    
    if [ "$USER_CHECKSUM" != "$REPO_CHECKSUM" ]; then
        echo "⚠️  Preserving existing user settings in hyprde.toml"
        echo "   User has customized configuration - keeping existing file"
        # Always copy scripts to ensure latest fixes are applied
        echo "🔄 Updating system scripts..."
        mkdir -p "$USER_HOME/.config/hypr/scripts"
        cp -rfp ./configs/hypr/scripts/* "$USER_HOME/.config/hypr/scripts/"
    else
        echo "📄 No user modifications detected - copying fresh config"
        cp -rfp ./configs/hypr $USER_HOME/.config
    fi
else
    # First time install - copy everything
    cp -rfp ./configs/hypr $USER_HOME/.config
fi

# Ensure the user owns the directory before running the build script
if [ -n "$SUDO_USER" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$USER_HOME/.config/hypr"
fi

echo "Generating dynamic Hyprland configuration from TOML..."

# Check if hyprexpo is enabled in user's config
if [ -f "$USER_HOME/.config/hypr/hyprde.toml" ]; then
    if ! grep -q 'enabled.*=.*\["hyprexpo"\]' "$USER_HOME/.config/hypr/hyprde.toml" 2>/dev/null; then
        echo "💡 Tip: hyprexpo plugin (workspace overview) can be enabled via settings."
        echo "   Press SUPER+C → Software Plugins → hyprexpo"
    fi
fi
if [ -n "$SUDO_USER" ]; then
    sudo -u "$SUDO_USER" HYPR_CONFIG_DIR="$USER_HOME/.config/hypr" python3 "$USER_HOME/.config/hypr/build_config.py"
else
    HYPR_CONFIG_DIR="$USER_HOME/.config/hypr" python3 "$USER_HOME/.config/hypr/build_config.py"
fi

backup_if_exists "$USER_HOME/.config/mako" "$BACKUP_DIR" "$USER_HOME"
cp -rfp ./configs/mako $USER_HOME/.config
# Set initial symlink for mako
ln -sf "$USER_HOME/.config/mako/config.dark" "$USER_HOME/.config/mako/config"

backup_if_exists "$USER_HOME/.config/waybar" "$BACKUP_DIR" "$USER_HOME"
cp -rfp ./configs/waybar $USER_HOME/.config

backup_if_exists "$USER_HOME/.config/wofi" "$BACKUP_DIR" "$USER_HOME"
cp -rfp ./configs/wofi $USER_HOME/.config

# Fix Wofi's relative CSS import by forcing the absolute user path
sed -i "s|@import \"../hypr/themes/current.css\";|@import \"$USER_HOME/.config/hypr/themes/current.css\";|g" "$USER_HOME/.config/wofi/style.css"

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
cp -rfp ./configs/applications/* $USER_HOME/.local/share/applications/

echo "Installing PolicyKit actions and authentication helpers..."
sudo mkdir -p /usr/share/polkit-1/actions
sudo cp -f ./configs/polkit/org.hyprde.recording.policy /usr/share/polkit-1/actions/

# Create unique symlinks to distinguish between different auth requests in PolicyKit
sudo ln -sf /usr/bin/true /usr/local/bin/hyprde-mic-auth
sudo ln -sf /usr/bin/true /usr/local/bin/hyprde-screen-auth

echo "Creating dedicated session menu directory..."
mkdir -p $USER_HOME/.local/share/hyprocket-session/applications

# Backup existing session menu entries if they exist
for app_file in ./configs/applications/*; do
    if [ -f "$app_file" ]; then
        app_name=$(basename "$app_file")
        backup_if_exists "$USER_HOME/.local/share/hyprocket-session/applications/$app_name" "$BACKUP_DIR" "$USER_HOME"
    fi
done
cp -rfp ./configs/applications/* $USER_HOME/.local/share/hyprocket-session/applications/

echo "Making scripts executable..."
chmod +x $USER_HOME/.config/hypr/scripts/*.sh
chmod +x $USER_HOME/.config/hypr/scripts/*.py
chmod +x $USER_HOME/.config/hypr/scripts/gammastep/*.sh

echo "Configuring passwordless TLP and privacy-preserving camera/mic toggle..."
TLP_PATH=$(which tlp 2>/dev/null || echo "/usr/bin/tlp")
MODPROBE_PATH=$(which modprobe 2>/dev/null || echo "/usr/bin/modprobe")
RMMOD_PATH=$(which rmmod 2>/dev/null || echo "/usr/bin/rmmod")
PACTL_PATH=$(which pactl 2>/dev/null || echo "/usr/bin/pactl")
SUDOERS_FILE="/etc/sudoers.d/hyprde-nopasswd"
# ALLOW (NOPASSWD): tlp (all), modprobe -r (removing camera), rmmod -f (force removing camera), pactl set-source-mute (muting mic)
# DENY (NOPASSWD): modprobe (adding camera), pactl set-source-mute (unmuting mic)
if [ -n "$SUDO_USER" ]; then
    printf "$SUDO_USER ALL=(ALL) NOPASSWD: $TLP_PATH\n$SUDO_USER ALL=(ALL) NOPASSWD: $MODPROBE_PATH -r uvcvideo\n$SUDO_USER ALL=(ALL) NOPASSWD: $RMMOD_PATH -f uvcvideo\n$SUDO_USER ALL=(ALL) NOPASSWD: $PACTL_PATH set-source-mute @DEFAULT_SOURCE@ on\n" | sudo tee "$SUDOERS_FILE" > /dev/null
    sudo chmod 440 "$SUDOERS_FILE"
else
    printf "$USER ALL=(ALL) NOPASSWD: $TLP_PATH\n$USER ALL=(ALL) NOPASSWD: $MODPROBE_PATH -r uvcvideo\n$USER ALL=(ALL) NOPASSWD: $RMMOD_PATH -f uvcvideo\n$USER ALL=(ALL) NOPASSWD: $PACTL_PATH set-source-mute @DEFAULT_SOURCE@ on\n" | tee "$SUDOERS_FILE" > /dev/null
    chmod 440 "$SUDOERS_FILE"
fi

echo "Creating wallpaper directories."
mkdir -p $USER_HOME/Pictures/wallpapers/morning
mkdir -p $USER_HOME/Pictures/wallpapers/noon
mkdir -p $USER_HOME/Pictures/wallpapers/evening
mkdir -p $USER_HOME/Pictures/wallpapers/favorites
echo "  Created: ~/Pictures/wallpapers/morning/   (6AM - 12PM)"
echo "  Created: ~/Pictures/wallpapers/noon/      (12PM - 6PM)"
echo "  Created: ~/Pictures/wallpapers/evening/   (6PM - 6AM)"
echo "  Created: ~/Pictures/wallpapers/favorites/ (for fixed mode)"

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

# Reload Hyprland configuration if running in a session
if command -v hyprctl >/dev/null 2>&1 && pgrep -x Hyprland >/dev/null 2>&1; then
    echo "Reloading Hyprland configuration..."
    if [ -n "$SUDO_USER" ]; then
        sudo -u "$SUDO_USER" hyprctl reload
    else
        hyprctl reload
    fi
fi

echo "You are ready to go.."