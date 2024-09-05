FROM archlinux

RUN pacman -Syu --noconfirm \
    xfce4 xfce4-goodies \
    sudo dbus xorg-server xorg-xinit \
    ly \
    ttf-dejavu ttf-liberation noto-fonts

RUN useradd -m user && echo "user ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER user
ENV HOME /home/user
CMD ["startxfce4"]