#!/bin/bash
# PC-BASIC install script for Linux

SPAWNED=$1

do_close () {
    if [ "$SPAWNED" = "spawned" ]; then
        echo "Press ENTER to exit."
        read KEY
    fi
    exit 0
}

abort () {
    echo "Installation aborted. No changes were made."
    do_close
}

cat pcbasic/info/VERSION
echo "INSTALLATION SCRIPT"
echo 

#default installation directory
DEFAULT_DIR="/opt/pcbasic/"
DESKTOP_DIR="/usr/share/applications"
ICON_DIR="/usr/share/icons"

if [ ! -t 1 ]; then 
	if [ "$SPAWNED" = "spawned"  -o  -z $DISPLAY  ]; then
		>&2 echo "This script must be run interactively."
        exit 1
	else
		xterm -e $0 spawned &
		exit
	fi  
fi

if [ "$(id -u)" != "0" ]; then
    echo -n "NOTE: You are running this script without root privileges, "
    echo "which means you can install PC-BASIC for your user only."
    echo "If you wish to install to a system-wide directory, run this script with root privileges using sudo $0" 1>&2
    echo
    
    DEFAULT_DIR="$HOME/pcbasic"
    
    # user's runtime data
    DATA_BASE_DIR=$XDG_DATA_HOME
    if [ -z "$DATA_BASE_DIR" ]; then
        DATA_BASE_DIR="$HOME/.local/share"
    fi
    DATA_DIR="$DATA_BASE_DIR/pcbasic"

    # user's config
    SETTINGS_DIR=$XDG_CONFIG_HOME
    if [ -z "$SETTINGS_DIR" ]; then
        SETTINGS_DIR="$HOME/.config"
    fi
    SETTINGS_DIR="$SETTINGS_DIR/pcbasic"

    DESKTOP_DIR="$DATA_BASE_DIR/applications"
    ICON_DIR="$DATA_BASE_DIR/icons"
fi

echo -n "In what directory would you like to install PC-BASIC (default: $DEFAULT_DIR) ? "
read INSTALL_DIR

if [ -z "$INSTALL_DIR" ]; then
    INSTALL_DIR="$DEFAULT_DIR"
fi

# check permissions
if [ ! -w $(dirname $INSTALL_DIR) ]; then
    echo
    echo -n "ERROR: You do not have permission to write to "
    dirname $INSTALL_DIR
    abort 
fi

UNINSTALLER="$INSTALL_DIR/uninstall.sh"

echo
echo "SUMMARY OF WHAT WILL BE DONE:"
echo "I will install PC-BASIC to directory $INSTALL_DIR"
if [ "$(id -u)" = "0" ]; then
    echo "I will create a symbolic link /usr/bin/pcbasic"
else
    echo "Your user settings will be stored in $SETTINGS_DIR"
    echo "Runtime data will be stored in $DATA_DIR"
fi

echo "I will create a desktop menu entry $DESKTOP_DIR/pcbasic.desktop"
echo "I will create an icon $ICON_DIR/pcbasic.png"
echo "I will create an uninstall script $UNINSTALLER"

echo
echo -n "Start installation [y/N] ? "
read ANSWER

if [ "$ANSWER" != "y" -a "$ANSWER" != "Y" ]; then
    abort
fi


echo
echo "Copying program files ... "
mkdir -p "$INSTALL_DIR"
cp -R pcbasic/* "$INSTALL_DIR"

if [ "$(id -u)" = "0" ]; then
    echo "Creating symlink ... "
    ln -s "$INSTALL_DIR/pcbasic" "/usr/bin/pcbasic"
fi

echo "Creating menu entry ... "
DESKTOP_FILE="$DESKTOP_DIR/pcbasic.desktop"
echo "[Desktop Entry]" > $DESKTOP_FILE
echo "Name=PC-BASIC 3.23" >> $DESKTOP_FILE
echo "GenericName=GW-BASIC compatible interpreter" >> $DESKTOP_FILE
echo "Exec=$INSTALL_DIR/pcbasic" >> $DESKTOP_FILE
echo "Terminal=false" >> $DESKTOP_FILE
echo "Type=Application" >> $DESKTOP_FILE
echo "Icon=pcbasic.png" >> $DESKTOP_FILE
echo "Categories=Development;IDE;" >> $DESKTOP_FILE

echo "Creating icon ... "
cp pcbasic.png "$ICON_DIR/pcbasic.png"

echo "Creating uninstaller ... "
echo "#!/bin/sh" > $UNINSTALLER
echo "echo \"UNINSTALL PC-BASIC\"" >> $UNINSTALLER
echo "echo" >> $UNINSTALLER
echo "echo -n \"Start un-installation [y/N] ? \"" >> $UNINSTALLER
echo "read ANSWER" >> $UNINSTALLER
echo "if [ \"$ANSWER\" != \"y\" -a \"$ANSWER\" != \"Y\" ]; then" >> $UNINSTALLER
echo "    exit 0" >> $UNINSTALLER
echo "fi" >> $UNINSTALLER
echo "echo"  >> $UNINSTALLER
echo "echo \"Removing icon ... \"" >> $UNINSTALLER
echo "rm $ICON_DIR/pcbasic.png" >> $UNINSTALLER
echo "echo \"Removing menu entry ... \"" >> $UNINSTALLER
echo "rm $DESKTOP_DIR/pcbasic.desktop" >> $UNINSTALLER
if [ "$(id -u)" = "0" ]; then
    echo "echo \"Removing symlink ... \"" >> $UNINSTALLER
    echo "rm /usr/bin/pcbasic" >> $UNINSTALLER
fi
echo "echo \"Removing program files ... \"" >> $UNINSTALLER
if [ -n "$INSTALL_DIR" ]; then
    echo "rm -r $INSTALL_DIR" >> $UNINSTALLER
fi
echo "echo" >> $UNINSTALLER
echo "echo \"UNINSTALL COMPLETED\"" >> $UNINSTALLER
chmod ugo+x $UNINSTALLER

echo
echo "INSTALLATION COMPLETED."
do_close

