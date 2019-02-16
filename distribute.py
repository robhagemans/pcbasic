#!/usr/bin/env python
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import sys
import json
from io import open

from setuptools import find_packages, setup

# we're not setup.py and not being called by the sdist installer
# so we can import from the package if we want
from pcbasic import VERSION, AUTHOR

# setup commands
from packaging import COMMANDS, package


# file location
HERE = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(HERE, 'setup.json'), encoding='utf-8') as setup_data:
    SETUP_DATA = json.load(setup_data)


SETUP_OPTIONS = dict(
    version=VERSION,
    author=AUTHOR,

    # contents
    # only include subpackages of pcbasic: exclude test, docsrc, packaging etc
    # even if these are excluded in the manifest, bdist_wheel will pick them up (but sdist won't)
    packages=find_packages(exclude=[_name for _name in os.listdir(HERE) if _name != 'pcbasic']),
    ext_modules=[],
    # include package data from MANIFEST.in (which is created by packaging script)
    include_package_data=True,
    # launchers
    entry_points=dict(
        console_scripts=['pcbasic=pcbasic:main'],
    ),

    **SETUP_DATA
)


if 'package' in sys.argv[1:]:
    package(**SETUP_OPTIONS)
elif 'bdist_wheel' in sys.argv[1:]:
    # universal wheel: same code works in py2 and py3, no C extensions
    setup(cmdclass=COMMANDS, script_args=sys.argv[1:]+['--universal'], **SETUP_OPTIONS)
elif set(sys.argv[1:]) & set(('sdist', 'build_docs', 'wash')):
    # universal wheel: same code works in py2 and py3, no C extensions
    setup(cmdclass=COMMANDS, **SETUP_OPTIONS)
else:
    sys.exit('supported commands: package, sdist, bdist_wheel, build_docs, wash')
