#!/usr/bin/env python3
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys

assert sys.version_info >= (3, 7), 'Packaging requires Python >= 3.7'

import os
import json
import subprocess

from .common import make_ready, make_docs, make_clean, make_local


if sys.platform == 'win32':
    from .windows import package
elif sys.platform == 'darwin':
    from .mac import package
else:
    from .linux import package

# usage:
if not sys.argv[1:]:
    package()
elif not sys.argv[2:]:
    if sys.argv[1] in ('build'):
        make_local()
        # universal wheel: same code works in py2 and py3, no C extensions
        subprocess.run([sys.executable, '-m', 'build'])
    elif sys.argv[1] == 'docs':
        make_docs()
    elif sys.argv[1] == 'local':
        make_local()
    elif sys.argv[1] == 'clean':
        make_clean()
    elif sys.argv[1] == 'ready':
        make_ready()
else:
    sys.exit("""USAGE:

   python3 -m make
   - build a distribution in this platform's native package format

   python3 -m make build
   - build a source distribution and a wheel

   python3 -m make docs
   - compile the documentation

   python3 -m make local
   - prepare for running from local directory

   python3 -m make ready
   - only prepare for a build

   python3 -m make clean
   - clean the workspace
""")
