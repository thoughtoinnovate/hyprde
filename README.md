# hyprde
out of box linux-hyprland-desktop
### Functions:

1. `package_string()`: Parses package names and installs them using `pacman`.
2. `install_packages()`: Installs packages based on the operating system distribution type.
3. `identifyOS()`: Identifies the distribution type (Arch Linux or Debian-based).

#### Steps:

1. The script prompts for root password at the start and installs the `yq` package as a prerequisite.
2. Reads a YAML configuration file (`config.yml`) and converts it to JSON using `yq`.
3. Parses JSON content using `jq` to extract package names.
4. Installs the extracted packages based on the distribution type (Arch Linux or Debian-based).
5. Copies configuration files from the `configs` directory to `$HOME/.config`.
6. Creates directories for wallpapers in `$HOME/Pictures/wallpapers/sunrise` and `$HOME/Pictures/wallpapers/sunset`.
7. Displays a message indicating the completion of the installation process.

#### Note:

- Ensure that the YAML configuration file (`config.yml`) is present in the script's directory.
- Customize the script as needed for additional package installations or configurations.