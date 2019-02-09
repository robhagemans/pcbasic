#!/usr/bin/env python
"""
PC-BASIC setup module

(c) 2015--2019 Rob Hagemans
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
include doc/*
include pcbasic/data/USAGE.txt
include pcbasic/data/release.json
include pcbasic/data/*/*
prune pcbasic/data/__pycache__
"""


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
# setup.py new commands
# see http://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setup-py.html


class Command(cmd.Command):
    """User command."""

    description = ''
    user_options = []

    def initialize_options(self):
        """Set default values for options."""
        pass

    def finalize_options(self):
        """Post-process options."""
        pass


class BuildDocCommand(Command):
    """Command to build the documentation."""

    description = 'build documentation files'

    def run(self):
        """Build documentation."""
        from docsrc import build_docs
        build_docs()


class WashCommand(Command):
    """Clean the workspace."""

    description = 'clean the workspace of build files; leave in-place compiled files'

    def run(self):
        """Clean the workspace."""
        # remove traces of egg
        for path in glob.glob(os.path.join(HERE, '*.egg-info')):
            _prune(path)
        # remove intermediate builds
        _prune(os.path.join(HERE, 'build'))
        # remove bytecode files
        for root, dirs, files in os.walk(HERE):
            for f in files:
                if f.endswith('.pyc') and 'test' not in root:
                    _remove(os.path.join(root, f))

def _prune(path):
    """Recursively remove a directory."""
    print('pruning %s' % (path, ))
    shutil.rmtree(path)

def _remove(path):
    """Remove a file."""
    print('removing %s' % (path, ))
    os.remove(path)


###############################################################################
# setup.py extended commands

class SDistCommand(sdist.sdist):
    """Custom sdist command."""

    def run(self):
        """Run sdist command."""
        with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
            f.write(DUNMANIFESTIN)
            f.write(
                u'include pcbasic/lib/README.md\n'
                u'prune test\n'
            )
        with open(os.path.join(HERE, 'pcbasic', 'data', 'release.json'), 'w') as f:
            f.write(json.dumps(RELEASE_ID).decode('ascii', 'ignore'))
        self.run_command('build_docs')
        sdist.sdist.run(self)
        os.remove(os.path.join(HERE, 'MANIFEST.in'))
        os.remove(os.path.join(HERE, 'pcbasic', 'data', 'release.json'))


class BuildPyCommand(build_py.build_py):
    """Custom build_py command."""

    def run(self):
        """Run build_py command."""
        with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
            f.write(DUNMANIFESTIN)
            f.write(u'prune test\n')
            # include DLLs on Windows
            if sys.platform == 'win32':
                if platform.architecture()[0] == '64bit':
                    f.write(u'include pcbasic/lib/win32_x64/*.dll\n')
                else:
                    f.write(u'include pcbasic/lib/win32_x86/*.dll\n')
        with open(os.path.join(HERE, 'pcbasic', 'data', 'release.json'), 'w') as f:
            f.write(json.dumps(RELEASE_ID).decode('ascii', 'ignore'))
        build_py.build_py.run(self)
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
            '*.txt', '*.md', 'pcbasic/*.txt', 'pcbasic/data/codepages/*',
            'pcbasic/data/fonts/*', 'pcbasic/data/programs/*',
            'pcbasic/lib/*',
        ],
    },
    'ext_modules': [],
    'include_package_data': True,

    # requirements
    # need Python 2.7.12+ or Python 3.5+
    'python_requires': '>=2.7.12,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*',
    'install_requires': ['numpy', 'pyserial', 'pyparallel'],
    # use e.g. pip install -e .[dev,full]
    'extras_require': {
        'dev': ['lxml', 'markdown', 'pylint', 'coverage', 'cx_Freeze'],
        'full': ['pygame', 'pyaudio'],
    },

    # launchers
    'entry_points': {
        'console_scripts':  ['pcbasic=pcbasic:main'],
        'gui_scripts': [],
    },

    # setup commands
    'cmdclass': {
        'build_docs': BuildDocCommand,
        'sdist': SDistCommand,
        'build_py': BuildPyCommand,
        'wash': WashCommand,
    },
}


# platform-specific settings
if sys.platform == 'win32':
    SETUP_OPTIONS['entry_points']['gui_scripts'] = ['pcbasicw=pcbasic:main']
elif sys.platform == 'linux2':
    target = '/usr/local/'
    SETUP_OPTIONS['data_files'] = [
        ('%s/share/man/man1/' % (target,), ['doc/pcbasic.1.gz']),
        ('%s/share/applications/' % (target,), ['icons/pcbasic.desktop']),
        ('%s/share/icons' % (target,), ['icons/pcbasic.png']),
    ]


###############################################################################
# run the setup

if __name__ == '__main__':
    setup(**SETUP_OPTIONS)
