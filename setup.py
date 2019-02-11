#!/usr/bin/env python
"""
PC-BASIC install script for source distribution

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
from io import open

from setuptools import find_packages, setup


###############################################################################
# get descriptions and version number

# file location
HERE = os.path.abspath(os.path.dirname(__file__))

# obtain metadata without importing the package (to avoid breaking setup)
with open(os.path.join(HERE, 'pcbasic', 'metadata.py'), encoding='utf-8') as f:
    exec(f.read())


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
    'packages': find_packages(exclude=['doc', 'test', 'docsrc', 'icons']),
    # rule of thumb for sdist: package_data specifies what gets *installed*,
    # but manifest specifies what gets *included* in the archive in the first place
    'package_data': {
        PACKAGE: [
            '*.txt', '*.md', 'pcbasic/*.txt',
            'pcbasic/data/*', 'pcbasic/data/*/*',
            # libs should be installed if included (in wheels)
            'pcbasic/lib/*',
        ],
    },
    'ext_modules': [],
    'include_package_data': True,

    # requirements
    # need Python 2.7.12+ or Python 3.5+
    'python_requires': '>=2.7.12,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    'install_requires': ['pyserial',],
    # use e.g. pip install -e .[dev,full]
    # pyparallel should be installed manually or through the distro if needed
    'extras_require': {
        'dev': ['lxml', 'markdown', 'pylint', 'coverage', 'cx_Freeze', 'Pillow', 'twine', 'wheel'],
        'full': ['pygame', 'pyaudio'],
    },

    # launchers
    'entry_points': {
        'console_scripts':  ['pcbasic=pcbasic:main'],
        'gui_scripts': [],
    },

}

if os.path.isdir('resources') and sys.platform.startswith('linux'):
    # these are for linux packaging only, but these files are simply not present otherwise
    SETUP_OPTIONS['data_files'] = [
        ('/usr/local/share/man/man1/', ['resources/pcbasic.1.gz']),
        ('/usr/local/share/applications/', ['resources/pcbasic.desktop']),
        ('/usr/local/share/icons', ['resources/pcbasic.png']),
    ]


###############################################################################
# run the setup

if __name__ == '__main__':

    # check we're not using the wrong script
    if set(sys.argv) & set((
            'bdist_wheel', 'sdist', 'bdist_rpm', 'bdist_deb', 'bdist_msi', 'bdist_dmg', 'build_docs'
        )):
        print(
            'setup.py is the install script only, please use package.py to build, package or deploy.'
        )
    else:
        # perform the installation
        setup(**SETUP_OPTIONS)
