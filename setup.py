#!/usr/bin/env python
"""
PC-BASIC install script for source distribution

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import json
from io import open

from setuptools import find_packages, setup


###############################################################################
# get descriptions and version number

# file location
HERE = os.path.abspath(os.path.dirname(__file__))

# obtain metadata without importing the package (to avoid breaking sdist install)
with open(os.path.join(HERE, 'pcbasic', 'basic', 'data', 'meta.json'), 'r') as meta:
    VERSION = json.load(meta)['version']

with open(os.path.join(HERE, 'pcbasic', 'metadata.py'), encoding='utf-8') as f:
    exec(f.read())

# files to exclude from packaging search - only include pcbasic/
TOP_EXCLUDE = [_name for _name in os.listdir(HERE) if _name != PACKAGE]


###############################################################################
# setup parameters

SETUP_OPTIONS = {
    # metadata
    'name': PACKAGE,
    'version': VERSION,
    'description': DESCRIPTION,
    'long_description': LONG_DESCRIPTION,
    'url': URL,
    'author': AUTHOR,
    'author_email': EMAIL,
    'license': LICENCE,
    'classifiers': CLASSIFIERS,
    'keywords': KEYWORDS,

    # contents
    # only include subpackages of pcbasic: exclude test, docsrc, packaging etc
    # even if these are excluded in the manifest, bdist_wheel will pick them up (but sdist won't)
    'packages': find_packages(exclude=TOP_EXCLUDE),
    'ext_modules': [],
    # include package data from MANIFEST.in (which is created by packaging script)
    'include_package_data': True,

    # launchers
    'entry_points': {
        'console_scripts':  ['pcbasic=pcbasic:main'],
        'gui_scripts': [],
    },

    # requirements
    # need Python 2.7.12+ or Python 3.5+
    'python_requires': '>=2.7.12,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    'install_requires': [],
    # use e.g. pip install -e .[dev,full]
    'extras_require': {
        # pyparallel misses giveio on pip - should be installed manually or through the distro if needed
        'ports': ['pyserial', 'pyparallel'],
        'full': ['pyserial', 'pyparallel', 'pygame', 'pyaudio'],
        'dev': ['lxml', 'markdown', 'pylint', 'coverage', 'cx_Freeze', 'Pillow', 'twine', 'wheel'],
    },
}

###############################################################################
# run the setup

if __name__ == '__main__':

    # check we're not using the wrong script
    if set(sys.argv) & set((
            'bdist_wheel', 'sdist', 'bdist_rpm', 'bdist_deb', 'bdist_msi', 'bdist_dmg', 'build_docs'
        )):
        print(
            'setup.py is the sdist install script only, '
            'please use distribute.py to build, package or deploy.'
        )
    else:
        # perform the installation
        setup(**SETUP_OPTIONS)
