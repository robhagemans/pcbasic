"""
PC-BASIC - make.linux
Linux packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import subprocess

import toml

from .common import make_clean, build_icon, make_docs, mkdir, prepare
from .common import HERE, VERSION


# project config
SETUP_DATA = toml.load(os.path.join(HERE, 'pyproject.toml'))['project']


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
    with open('resources/pcbasic.desktop', 'w') as xdg_file:
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
    with open('resources/control', 'w') as control_file:
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
    make_clean()
    mkdir('resources')
    build_desktop_file()
    build_deb_control_file()
    build_icon()
    make_docs()


def package():
    """Build Linux packages."""
    prepare()
    subprocess.run(['python3.7', '-m', 'build'])
    build_resources()
    subprocess.run(f'make/makedeb.sh {VERSION}', shell=True)
