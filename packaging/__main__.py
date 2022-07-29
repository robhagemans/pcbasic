#!/usr/bin/env python3
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2022 Rob Hagemans
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

from .common import COMMANDS, SETUP_OPTIONS

if sys.platform == 'win32':
    from .windows import package
elif sys.platform == 'darwin':
    from .mac import package
else:
    from . import linux

# usage:
if not sys.argv[1:]:
    package(**SETUP_OPTIONS)
elif 'bdist_wheel' in sys.argv[1:]:
    # universal wheel: same code works in py2 and py3, no C extensions
    setup(cmdclass=COMMANDS, script_args=sys.argv[1:]+['--universal'], **SETUP_OPTIONS)
elif set(sys.argv[1:]) & set(('sdist', 'build_docs', 'wash', 'build_resources')):
    setup(cmdclass=COMMANDS, **SETUP_OPTIONS)
else:
    sys.exit("""USAGE:

   python3 -m packaging
   - build a distribution in this platform's native package format

   python3 -m packaging sdist
   - build a source distribution

   python3 -m packaging bdist_wheel
   - build a wheel

   python3 -m packaging build_docs
   - compile the documentation

   python3 -m packaging wash
   - clean the workspace
""")
