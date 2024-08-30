#!/bin/bash

#Function to create package string
package_string(){
    if [ -z "$1" ];then
     echo "Package names not parsable!"
     exit 1
    fi
    local packages=$@
    echo "Packages $packages"
    jq_pkgs=$(echo $packages|jq '.[]')
    for package in $jq_pkgs; do
       package=$(echo "$package"|sed 's/^"//;s/"$//')
       echo "Installlig $package"
       sudo pacman -S --needed $package
    done
    
    echo "------------"
    echo $delimited_packages

}

# Function to install yq using pacman
install_packages() {

    if [ "$#" -eq 0 ];then
        "Software package to install is missing!"
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
                echo "Unsupported distribution: $ID"
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
            ;;
    esac
else
    echo "/etc/os-release file not found. Unable to determine the distribution type."
fi
}

# Prompt for root password at the start
echo "Need priviledges for installation of packages..."
sudo echo "Installation Started..."
# Read the TOML file and convert it to JSON
CONFIG_FILE="config.yml"
JSON_CONTENT=$(yq < "$CONFIG_FILE")

# Parse JSON content using jq (which is part of yq)
DEFAULTS=$(echo "$JSON_CONTENT" |jq -r '.configs.[].packages.[]')

echo "Installing Prerequisites..."
install_packages $DEFAULTS
echo "Copying config Files ......"
cp -rf ./configs  $HOME/.config
echo "Creating wallpaersdirectories."
mkdir -p $HOME/Pictures/wallpapers/sunrise
mkdir -p $HOME/Pictures/wallpapers/sunset
echo "You are ready to go.."


