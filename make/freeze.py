"""
PC-BASIC make.freeze
common definitions for cx_Freeze packaging utilities

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os

from distutils.util import get_platform
from setuptools import find_packages
from setuptools.command import sdist, build_py

from .common import VERSION, AUTHOR
from .common import HERE


SHORT_VERSION = u'.'.join(VERSION.split('.')[:2])

# platform tag (build directories etc.)
PLATFORM_TAG = '{}-{}.{}'.format(
    get_platform(), sys.version_info.major, sys.version_info.minor
)

# non-python files to include
INCLUDE_FILES = (
    '*.md',
    '*.txt',
    'pcbasic/data/',
    'pcbasic/basic/data/',
)

# python files to exclude from distributions
EXCLUDE_FILES = (
    'tests/', 'make/', 'docs/',
)
EXCLUDE_PACKAGES=[
    _name+'*' for _name in os.listdir(HERE) if _name != 'pcbasic'
]

EXCLUDE_EXTERNAL_PACKAGES = [
    'pygame',
    'pip', 'wheel', 'unittest', 'pydoc_data',
    'email', 'xml',
]

SETUP_OPTIONS = dict(
    name="pcbasic",
    version=VERSION,
    author=AUTHOR,
    # contents
    # only include subpackages of pcbasic: exclude tests, docs, make etc
    packages=find_packages(exclude=EXCLUDE_PACKAGES),
    ext_modules=[],
    include_package_data=True,
    # launchers
    entry_points=dict(
        console_scripts=['pcbasic=pcbasic:main'],
    ),
)
