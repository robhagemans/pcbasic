#!/usr/bin/env python3
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
assert sys.version_info >= (3, 7), 'Packaging requires Python >= 3.7'

import os
import json
import subprocess

from .common import SETUP_OPTIONS, prepare, build_docs, wash


if sys.platform == 'win32':
    from .windows import package
elif sys.platform == 'darwin':
    from .mac import package
else:
    from .linux import package

# usage:
if not sys.argv[1:]:
    package(**SETUP_OPTIONS)
elif not sys.argv[2:]:
    if sys.argv[1] in ('wheel', 'bdist_wheel', 'sdist', 'build'):
        prepare()
        # universal wheel: same code works in py2 and py3, no C extensions
        subprocess.run(['python3.7', '-m', 'build'])
    elif sys.argv[1] == 'build_docs':
        build_docs()
    elif sys.argv[1] == 'wash':
        wash()
else:
    sys.exit("""USAGE:

   python3 -m make
   - build a distribution in this platform's native package format

   python3 -m make sdist
   - build a source distribution

   python3 -m make bdist_wheel
   - build a wheel

   python3 -m make build_docs
   - compile the documentation

   python3 -m make wash
   - clean the workspace
""")
