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

# Prompt for root password at the start
echo "Need priviledges for installation of packages..."
sudo echo "Installation Started..."
echo "Installing Prerequisites..."
install_packages yq
# Read the YAML file and convert it to JSON
CONFIG_FILE="config.yml"
JSON_CONTENT=$(yq < "$CONFIG_FILE")

# Parse JSON content using jq (which is part of yq)
PKGS="gdk-pixbuf2 $(echo "$JSON_CONTENT" |jq -r '.configs[].packages[]')"
echo "Now installing $PKGS"
install_packages $PKGS
echo "Copying config Files ......"
cp -rf ./configs/alacritty $HOME/.config
cp -rf ./configs/hypr $HOME/.config
cp -rf ./configs/mako $HOME/.config
cp -rf ./configs/waybar $HOME/.config
cp -rf ./configs/wofi $HOME/.config
cp ./configs/mimeapps.list $HOME/.config/

# Update desktop database
update-desktop-database

# Set default MIME associations
xdg-mime default org.pwmt.zathura.desktop application/pdf
xdg-mime default imv.desktop image/png image/jpeg image/gif image/bmp image/tiff image/webp
xdg-mime default mpv.desktop video/mp4 video/avi video/mkv video/webm audio/mp3 audio/flac audio/wav

echo "Copying desktop entries..."
mkdir -p $HOME/.local/share/applications
cp -rf ./configs/applications/* $HOME/.local/share/applications/

echo "Creating dedicated session menu directory..."
mkdir -p $HOME/.local/share/hyprde-session/applications
cp -rf ./configs/applications/* $HOME/.local/share/hyprde-session/applications/

echo "Making scripts executable..."
chmod +x $HOME/.config/hypr/scripts/*.sh
chmod +x $HOME/.config/hypr/scripts/gammastep/*.sh

echo "Creating logout script in PATH..."
mkdir -p $HOME/.local/bin
cat > $HOME/.local/bin/hyprde-logout << 'EOF'
#!/bin/bash
$HOME/.config/hypr/scripts/wofi_session.sh logout
EOF
chmod +x $HOME/.local/bin/hyprde-logout

echo "Adding ~/.local/bin to PATH..."
if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' $HOME/.bashrc; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> $HOME/.bashrc
fi
echo "Creating wallpaper directories."
mkdir -p $HOME/Pictures/wallpapers/sunrise
mkdir -p $HOME/Pictures/wallpapers/sunset
echo "You are ready to go.."