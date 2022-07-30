#!/usr/bin/env python3
"""
PC-BASIC make.common
Python, Windows, MacOS and Linux packaging utilities

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import shutil
import glob
import json
import datetime
from subprocess import check_output, CalledProcessError
from contextlib import contextmanager
from io import open
from distutils.util import get_platform
from distutils import cmd

from setuptools import find_packages
from setuptools.command import sdist, build_py
from wheel import bdist_wheel
from PIL import Image

# we're not setup.py and not being called by the sdist installer
# so we can import from the package if we want
from pcbasic import NAME, VERSION, AUTHOR, COPYRIGHT
from pcbasic.basic.data import ICON
from pcbasic.compat import int2byte


# root location
HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

with open(os.path.join(HERE, 'setup.json'), encoding='utf-8') as setup_data:
    SETUP_DATA = json.load(setup_data)

# platform tag (build directories etc.)
PLATFORM_TAG = '{}-{}.{}'.format(
    get_platform(), sys.version_info.major, sys.version_info.minor
)

SHORT_VERSION = u'.'.join(VERSION.split('.')[:2])

# git commit hash
try:
    TAG = check_output(['git', 'describe', '--tags'], cwd=HERE).strip().decode('ascii', 'ignore')
    COMMIT = check_output(
        ['git', 'describe', '--always'], cwd=HERE
    ).strip().decode('ascii', 'ignore')
except (EnvironmentError, CalledProcessError):
    TAG = u''
    COMMIT = u''

# release info
RELEASE_ID = {
    u'version': VERSION,
    u'tag': TAG,
    u'commit': COMMIT,
    u'timestamp': str(datetime.datetime.now())
}

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
    # only include subpackages of pcbasic: exclude tests, docsrc, make etc
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

###############################################################################
# icon

def build_icon():
    """Create an icon file for the present platform."""
    try:
        os.mkdir('resources')
    except EnvironmentError:
        pass
    # build icon
    flat = (_b for _row in ICON for _b in _row)
    rgb = ((_b*255,)*3 for _b in flat)
    rgbflat = (_b for _tuple in rgb for _b in _tuple)
    imgstr = b''.join(int2byte(_b) for _b in rgbflat)
    width, height = len(ICON[0]), len(ICON)
    img = Image.frombytes('RGB', (width, height), imgstr)
    format = {'win32': 'ico', 'darwin': 'icns'}.get(sys.platform, 'png')
    img.resize((width*2, height*2)).save('resources/pcbasic.%s' % (format,))


###############################################################################
# setup.py new/extended commands
# see http://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setup-py.html

def new_command(function):
    """Add a custom command without having to faff around with an overbearing API."""

    class _NewCommand(cmd.Command):
        description = function.__doc__
        user_options = []
        def run(self):
            function()
        def initialize_options(self):
            pass
        def finalize_options(self):
            pass

    return _NewCommand

def extend_command(parent, function):
    """Extend an existing command."""

    class _ExtCommand(parent):
        def run(self):
            function(self)

    return _ExtCommand

@contextmanager
def os_safe(message, name):
    """Catch and report environment errors."""
    print('... {} {} ... '.format(message, name), end='')
    try:
        yield
    except EnvironmentError as err:
        print(err)
    else:
        print('ok')


def prune(path):
    """Recursively remove a directory."""
    with os_safe('pruning', path):
        shutil.rmtree(path)

def remove(path):
    """Remove a file."""
    with os_safe('removing', path):
        os.remove(path)

def mkdir(name):
    """Create a directory and all parents needed (mkdir -p)."""
    with os_safe('creating', name):
        os.makedirs(name)

def stamp_release():
    """Place the relase ID file."""
    json_str = json.dumps(RELEASE_ID)
    if isinstance(json_str, bytes):
        json_str = json_str.decode('ascii', 'ignore')
    with open(os.path.join(HERE, 'pcbasic', 'basic', 'data', 'release.json'), 'w') as release_json:
        release_json.write(json_str)

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


def build_docs():
    """build documentation files"""
    import docsrc
    docsrc.build_docs()

def wash():
    """clean the workspace of build files; leave in-place compiled files"""
    # remove traces of egg
    for path in glob.glob(os.path.join(HERE, '*.egg-info')):
        prune(path)
    # remove intermediate builds
    prune(os.path.join(HERE, 'build'))
    # remove bytecode files
    for root, dirs, files in os.walk(HERE):
        for name in dirs:
            if name == '__pycache__':
                prune(os.path.join(root, name))
        for name in files:
            if (name.endswith('.pyc') or name.endswith('.pyo')) and 'test' not in root:
                remove(os.path.join(root, name))
    # remove distribution resources
    prune(os.path.join(HERE, 'resources'))
    # remove release stamp
    remove(os.path.join(HERE, 'pcbasic', 'basic', 'data', 'release.json'))
    # remove manifest
    remove(os.path.join(HERE, 'MANIFEST.in'))

def sdist_ext(obj):
    """Run custom sdist command."""
    wash()
    stamp_release()
    build_manifest(INCLUDE_FILES + ('pcbasic/lib/README.md',), EXCLUDE_FILES)
    build_docs()
    sdist.sdist.run(obj)
    wash()

def bdist_wheel_ext(obj):
    """Run custom bdist_wheel command."""
    wash()
    build_docs()
    # bdist_wheel calls build_py which does stamp_release() and build_docs()
    bdist_wheel.bdist_wheel.run(obj)
    wash()

def build_py_ext(obj):
    """Run custom build_py command."""
    stamp_release()
    build_manifest(INCLUDE_FILES + ('pcbasic/lib/*/*',), EXCLUDE_FILES)
    build_py.build_py.run(obj)


# setup commands
COMMANDS = {
    'build_docs': new_command(build_docs),
    'sdist': extend_command(sdist.sdist, sdist_ext),
    'build_py': extend_command(build_py.build_py, build_py_ext),
    'bdist_wheel': extend_command(bdist_wheel.bdist_wheel, bdist_wheel_ext),
    'wash': new_command(wash),
}
