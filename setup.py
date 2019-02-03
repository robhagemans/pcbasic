#!/usr/bin/env python
"""
PC-BASIC setup module

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import platform
import shutil
import glob
import datetime
import json
from io import open
from subprocess import check_output, CalledProcessError

from distutils import cmd
from setuptools.command import sdist, build_py
from setuptools import find_packages, Extension, setup


# file location
HERE = os.path.abspath(os.path.dirname(__file__))

# this is the base MANIFEST.in
# but I need it to change for different platforms/commands
DUNMANIFESTIN = u"""
include *.md
include GPL3.txt
include doc/*.html
include pcbasic/data/USAGE.txt
include pcbasic/data/release.json
include pcbasic/data/*/*
prune pcbasic/data/__pycache__
"""

# indicates that setup.py is being called by fpm
_FPM = False

###############################################################################
# get descriptions and version number

# obtain metadata without importing the package (to avoid breaking setup)
with open(os.path.join(HERE, 'pcbasic', 'metadata.py'), encoding='utf-8') as f:
    exec(f.read())


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
    """Extend an exitsing command."""

    class _ExtCommand(parent):
        def run(self):
            function(self)

    return _ExtCommand


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
    for root, _, files in os.walk(HERE):
        for name in files:
            if (name.endswith('.pyc') or name.endswith('.pyo')) and 'test' not in root:
                _remove(os.path.join(root, name))

def _prune(path):
    """Recursively remove a directory."""
    print('pruning %s' % (path, ))
    try:
        shutil.rmtree(path)
    except EnvironmentError as e:
        print(e)

def _remove(path):
    """Remove a file."""
    print('removing %s' % (path, ))
    try:
        os.remove(path)
    except EnvironmentError as e:
        print(e)

def sdist_ext(obj):
    """Run custom sdist command."""
    wash()
    with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
        f.write(DUNMANIFESTIN)
        f.write(
            u'include pcbasic/lib/README.md\n'
            u'prune test\n'
        )
    with open(os.path.join(HERE, 'pcbasic', 'data', 'release.json'), 'w') as f:
        json_str = json.dumps(RELEASE_ID)
        if isinstance(json_str, bytes):
            json_str = json_str.decode('ascii', 'ignore')
        f.write(json_str)
    build_docs()
    sdist.sdist.run(obj)
    os.remove(os.path.join(HERE, 'MANIFEST.in'))
    os.remove(os.path.join(HERE, 'pcbasic', 'data', 'release.json'))
    wash()

def build_py_ext(obj):
    """Run custom build_py command."""
    with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
        f.write(DUNMANIFESTIN)
        f.write(u'prune test\n')
        if not _FPM:
            # include binary libraries for Windows & Mac in wheel
            f.write(u'include pcbasic/lib/*/*\n')
    with open(os.path.join(HERE, 'pcbasic', 'data', 'release.json'), 'w') as f:
        json_str = json.dumps(RELEASE_ID)
        if isinstance(json_str, bytes):
            json_str = json_str.decode('ascii', 'ignore')
        f.write(json_str)
    build_py.build_py.run(obj)
    os.remove(os.path.join(HERE, 'MANIFEST.in'))
    os.remove(os.path.join(HERE, 'pcbasic', 'data', 'release.json'))


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
    'install_requires': ['pyserial', 'pyparallel'],
    # use e.g. pip install -e .[dev,full]
    'extras_require': {
        'dev': ['lxml', 'markdown', 'pylint', 'coverage', 'cx_Freeze'],
        'full': ['pygame', 'pyaudio'],
    },

    # launchers
    'entry_points': {
        'console_scripts':  ['pcbasic=pcbasic:main'],
        # this is needed for Windows only, but we create only one wheel
        'gui_scripts': ['pcbasicw=pcbasic:main'],
    },

    # setup commands
    'cmdclass': {
        'build_docs': new_command(build_docs),
        'sdist': extend_command(sdist.sdist, sdist_ext),
        'build_py': extend_command(build_py.build_py, build_py_ext),
        'wash': new_command(wash),
    },
}


if '--called-by-fpm' in sys.argv:
    # these need to be included in the sdist metadata for the packaging script to pick them up
    # we ask fpm to include a special argument to avoid breaking other calls

    sys.argv.remove('--called-by-fpm')

    _FPM = True
    _TARGET = '/usr/local/'

    SETUP_OPTIONS['data_files'] = [
        ('%s/share/man/man1/' % (_TARGET,), ['resources/pcbasic.1.gz']),
        ('%s/share/applications/' % (_TARGET,), ['resources/pcbasic.desktop']),
        ('%s/share/icons' % (_TARGET,), ['resources/pcbasic.png']),
    ]


###############################################################################
# run the setup

if __name__ == '__main__':
    setup(**SETUP_OPTIONS)
