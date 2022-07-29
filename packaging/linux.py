"""
PC-BASIC - packaging.linux
Linux packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import shutil
import subprocess
from io import open

from setuptools import setup

from .common import wash, new_command, build_icon, build_docs, wash, stamp_release, mkdir
from .common import COMMANDS

XDG_DESKTOP_ENTRY = {
    u'Name': u'PC-BASIC',
    u'GenericName': u'GW-BASIC compatible interpreter',
    u'Exec': u'/usr/local/bin/pcbasic',
    u'Terminal': u'false',
    u'Type': u'Application',
    u'Icon': u'pcbasic',
    u'Categories': u'Development;IDE;',
}

def build_desktop_file():
    """Build .desktop file."""
    with open('resources/pcbasic.desktop', 'w') as xdg_file:
        xdg_file.write(u'[Desktop Entry]\n')
        xdg_file.write(u'\n'.join(
            u'{}={}'.format(_key, _value)
            for _key, _value in XDG_DESKTOP_ENTRY.items()
        ))
        xdg_file.write(u'\n')

def build_resources():
    """Build desktop and package resources."""
    wash()
    stamp_release()
    mkdir('resources')
    build_desktop_file()
    build_icon()
    build_docs()

COMMANDS.update(dict(build_resources=new_command(build_resources)))
