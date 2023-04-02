"""
PC-BASIC - make.linux
Linux packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import subprocess

import toml

from .common import make_clean, build_icon, make_docs, mkdir, make_ready
from .common import VERSION, HERE, RESOURCE_PATH


# project config
SETUP_DATA = toml.load(os.path.join(HERE, 'pyproject.toml'))['project']

# paths
CONTROL_FILE = os.path.join(RESOURCE_PATH, 'control')
DESKTOP_FILE = os.path.join(RESOURCE_PATH, 'pcbasic.desktop')


def build_desktop_file():
    """Build .desktop file."""
    XDG_DESKTOP_ENTRY = """\
[Desktop Entry]
Name=PC-BASIC
GenericName=GW-BASIC compatible interpreter
Exec=/usr/local/bin/pcbasic
Terminal=false
Type=Application
Icon=pcbasic
Categories=Development;IDE;
"""
    with open(DESKTOP_FILE, 'w') as xdg_file:
        xdg_file.write(XDG_DESKTOP_ENTRY)


def build_deb_control_file():
    """Build control file for deb package."""
    CONTROL_PATTERN = """\
Package: python3-pcbasic
Version: {version}
License: {license}
Vendor: none
Architecture: all
Maintainer: <{author_email}>
Depends: python3-pkg-resources,python3-serial,python3-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0
Section: default
Priority: extra
Homepage: {url}
Description: {description}
"""
    with open(CONTROL_FILE, 'w') as control_file:
        control_file.write(CONTROL_PATTERN.format(
            license=SETUP_DATA['license']['text'],
            author_email=SETUP_DATA['authors'][0]['email'],
            url=SETUP_DATA['urls']['Homepage'],
            version=VERSION,
            description=SETUP_DATA['description']
        )
    )


def build_resources():
    """Build desktop and package resources."""
    mkdir(RESOURCE_PATH)
    build_desktop_file()
    build_deb_control_file()
    build_icon()


def package():
    """Build Linux packages."""
    make_ready()
    subprocess.run([sys.executable, '-m', 'build'])
    build_resources()
    subprocess.run(f'make/makedeb.sh {VERSION}', shell=True)
