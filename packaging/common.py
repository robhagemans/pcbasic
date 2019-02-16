#!/usr/bin/env python
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import shutil
import glob
import json
import subprocess
import datetime
import time
from subprocess import check_output, CalledProcessError
from contextlib import contextmanager
from io import open
from distutils.util import get_platform
from distutils import cmd
import distutils

from setuptools.command import sdist, build_py
from wheel import bdist_wheel
from PIL import Image

# we're not setup.py and not being called by the sdist installer
# so we can import from the package if we want
from pcbasic import NAME, VERSION, AUTHOR, COPYRIGHT
from pcbasic.data import ICON
from pcbasic.compat import int2byte


# root location
HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

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
    'distribute.py', 'test/', 'packaging/', 'docsrc/', 'fontsrc/'
)

###############################################################################
# icon

def _build_icon():
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
    except EnvironmentError as e:
        print(e)
    else:
        print('ok')


def _prune(path):
    """Recursively remove a directory."""
    with os_safe('pruning', path):
        shutil.rmtree(path)

def _remove(path):
    """Remove a file."""
    with os_safe('removing', path):
        os.remove(path)

def _mkdir(name):
    """Create a directory."""
    with os_safe('creating', name):
        os.mkdir(name)

def _stamp_release():
    """Place the relase ID file."""
    with open(os.path.join(HERE, 'pcbasic', 'data', 'release.json'), 'w') as f:
        json_str = json.dumps(RELEASE_ID)
        if isinstance(json_str, bytes):
            json_str = json_str.decode('ascii', 'ignore')
        f.write(json_str)

def _build_manifest(includes, excludes):
    """Build the MANIFEST.in."""
    manifest = u''.join(
        u'include {}\n'.format(_inc) for _inc in includes if not _inc.endswith('/')
    ) + u''.join(
        u'graft {}\n'.format(_inc) for _inc in includes if _inc.endswith('/')
    ) + u''.join(
        u'exclude {}\n'.format(_exc) for _exc in excludes if not _exc.endswith('/')
    ) + u''.join(
        u'prune {}\n'.format(_exc) for _exc in excludes if _exc.endswith('/')
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
        _prune(path)
    # remove intermediate builds
    _prune(os.path.join(HERE, 'build'))
    # remove bytecode files
    for root, dirs, files in os.walk(HERE):
        for name in dirs:
            if name == '__pycache__':
                _prune(os.path.join(root, name))
        for name in files:
            if (name.endswith('.pyc') or name.endswith('.pyo')) and 'test' not in root:
                _remove(os.path.join(root, name))
    # remove distribution resources
    _prune(os.path.join(HERE, 'resources'))
    # remove release stamp
    _remove(os.path.join(HERE, 'pcbasic', 'data', 'release.json'))
    # remove manifest
    _remove(os.path.join(HERE, 'MANIFEST.in'))

def sdist_ext(obj):
    """Run custom sdist command."""
    wash()
    _stamp_release()
    _build_manifest(INCLUDE_FILES + ('pcbasic/lib/README.md',), EXCLUDE_FILES)
    build_docs()
    sdist.sdist.run(obj)
    wash()

def bdist_wheel_ext(obj):
    """Run custom bdist_wheel command."""
    wash()
    build_docs()
    # bdist_wheel calls build_py
    bdist_wheel.bdist_wheel.run(obj)
    wash()

def build_py_ext(obj):
    """Run custom build_py command."""
    _stamp_release()
    _build_manifest(INCLUDE_FILES + ('pcbasic/lib/*/*',), EXCLUDE_FILES)
    build_py.build_py.run(obj)


# setup commands
COMMANDS = {
    'build_docs': new_command(build_docs),
    'sdist': extend_command(sdist.sdist, sdist_ext),
    'build_py': extend_command(build_py.build_py, build_py_ext),
    'bdist_wheel': extend_command(bdist_wheel.bdist_wheel, bdist_wheel_ext),
    'wash': new_command(wash),
}
