#!/usr/bin/env python3
"""
PC-BASIC install script for source distribution

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import json
from io import open

from setuptools import find_packages, setup

# check we're not using the wrong script
if set(sys.argv) & set((
        'bdist_wheel', 'sdist', 'bdist_rpm', 'bdist_deb', 'bdist_msi', 'bdist_dmg', 'build_docs'
    )):
    sys.exit(
        'setup.py is the sdist install script only, '
        'please use `python -m packaging` to build, package or deploy.'
    )

###############################################################################
# get descriptions and version number

# file location
HERE = os.path.abspath(os.path.dirname(__file__))

# obtain metadata without importing the package (to avoid breaking sdist install)
with open(os.path.join(HERE, 'pcbasic', 'basic', 'data', 'meta.json'), 'r') as meta:
    _METADATA = json.load(meta)
    VERSION = _METADATA['version']
    AUTHOR = _METADATA['author']


###############################################################################
# setup parameters

SETUP_OPTIONS = dict(
    name='pcbasic',
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
)

###############################################################################
# run the setup

# perform the installation
setup(**SETUP_OPTIONS)
