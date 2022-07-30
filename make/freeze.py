#!/usr/bin/env python3
"""
PC-BASIC make.freeze
common definitions for cx_Freeze packaging utilities

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from distutils.util import get_platform
from setuptools import find_packages

from .common import VERSION, AUTHOR, SETUP_DATA, HERE


SHORT_VERSION = u'.'.join(VERSION.split('.')[:2])

# platform tag (build directories etc.)
PLATFORM_TAG = '{}-{}.{}'.format(
    get_platform(), sys.version_info.major, sys.version_info.minor
)

# non-python files to include
INCLUDE_FILES = (
    '*.md',
    '*.txt',
    'doc/*.html',
    'pcbasic/data/',
    'pcbasic/basic/data/',
)

# python files to exclude from distributions
EXCLUDE_FILES = (
    'tests/', 'make/', 'docsrc/', 'fontsrc/',
)
EXCLUDE_PACKAGES=[
    _name+'*' for _name in os.listdir(HERE) if _name != 'pcbasic'
]

SETUP_OPTIONS = dict(
    version=VERSION,
    author=AUTHOR,

    # contents
    # only include subpackages of pcbasic: exclude tests, docsrc, packaging etc
    # even if these are excluded in the manifest, bdist_wheel will pick them up (but sdist won't)
    packages=find_packages(exclude=EXCLUDE_PACKAGES),
    ext_modules=[],
    # include package data from MANIFEST.in (which is created by packaging script)
    include_package_data=True,
    # launchers
    entry_points=dict(
        console_scripts=['pcbasic=pcbasic:main'],
    ),

    **SETUP_DATA
)

def build_manifest(includes, excludes):
    """Build the MANIFEST.in."""
    manifest = u''.join(
        u'include {}\n'.format(_inc) for _inc in includes if not _inc.endswith('/')
    ) + u''.join(
        u'graft {}\n'.format(_inc[:-1]) for _inc in includes if _inc.endswith('/')
    ) + u''.join(
        u'exclude {}\n'.format(_exc) for _exc in excludes if not _exc.endswith('/')
    ) + u''.join(
        u'prune {}\n'.format(_exc[:-1]) for _exc in excludes if _exc.endswith('/')
    )
    with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as manifest_file:
        manifest_file.write(manifest)
