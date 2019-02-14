#!/usr/bin/env python
"""
PC-BASIC packaging script
Python, Windows, MacOS and Linux packaging

(c) 2015--2020 Rob Hagemans
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
from PIL import Image

# get setup.py parameters
from setup import SETUP_OPTIONS

# we're not setup.py and not being called by the sdist installer
# so we can import form the package if we want
from pcbasic.metadata import NAME, AUTHOR, VERSION, COPYRIGHT
from pcbasic.data import ICON
from pcbasic.compat import int2byte


# operating in cx_Freeze mode
CX_FREEZE = set(sys.argv) & set(('bdist_msi', 'bdist_dmg', 'bdist_mac', 'build_exe'))

if CX_FREEZE:
    import cx_Freeze
    from cx_Freeze import setup, Executable
else:
    from setuptools import setup


# file location
HERE = os.path.abspath(os.path.dirname(__file__))

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
    'GPL3.txt',
    'doc/*.html',
    'pcbasic/data/USAGE.txt',
    'pcbasic/data/release.json',
    'pcbasic/data/*/*',
)

# python files to exclude from distributions
EXCLUDE_FILES = (
    'package.py', 'test/',
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
    """Extend an exitsing command."""

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
        u'include {}\n'.format(_inc) for _inc in includes
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
    for root, _, files in os.walk(HERE):
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

def build_py_ext(obj):
    """Run custom build_py command."""
    _stamp_release()
    _build_manifest(INCLUDE_FILES + ('pcbasic/lib/*/*',), EXCLUDE_FILES)
    #build_docs()
    build_py.build_py.run(obj)


# setup commands
SETUP_OPTIONS['cmdclass'] = {
    'build_docs': new_command(build_docs),
    'sdist': extend_command(sdist.sdist, sdist_ext),
    'build_py': extend_command(build_py.build_py, build_py_ext),
    'wash': new_command(wash),
}



###############################################################################
# Windows

if CX_FREEZE and sys.platform == 'win32':

    from packaging.windows import package

    package(SETUP_OPTIONS, NAME, AUTHOR, VERSION, SHORT_VERSION, COPYRIGHT)


###############################################################################
# Mac

elif CX_FREEZE and sys.platform == 'darwin':

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            # include dylibs
            _build_manifest(INCLUDE_FILES + ('pcbasic/lib/darwin/*',), EXCLUDE_FILES)
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    # remove tests and examples
                    # remove windows DLLs and PYDs
                    if (testing or 'win32_' in name or name.endswith('.dll')):
                        _remove(name)
            # remove modules that can be left out
            for module in ('distutils', 'setuptools', 'pydoc_data'):
                _prune(build_dir + 'lib/%s' % module)


    class BdistMacCommand(cx_Freeze.bdist_mac):
        """Custom bdist_mac command."""

        def run(self):
            """Run bdist_mac command."""
            cx_Freeze.bdist_mac.run(self)
            # fix install names in libraries in lib/ that were modified by cx_Freeze
            name = 'libSDL2_gfx.dylib'
            file_path = 'build/PC-BASIC-2.0.app/Contents/MacOS/lib/pcbasic/lib/darwin/' + name
            subprocess.call((
                'install_name_tool', '-change', '@executable_path/libSDL2.dylib',
                '@loader_path/libSDL2.dylib', file_path
            ))
            # remove some files we don't need
            _remove('build/PC-BASIC-2.0.app/Contents/MacOS/libSDL2.dylib')
            for path in glob.glob('build/PC-BASIC-2.0.app/Contents/MacOS/libnpymath*'):
                _remove(path)

        def copy_file(self, src, dst):
            # catch copy errors, these happen with relative references with funny bracketed names
            # like libnpymath.a(npy_math.o)
            try:
                cx_Freeze.bdist_mac.copy_file(self, src, dst)
            except Exception as e:
                print('ERROR: %s' % (e,))
                # create an empty file
                open(dst, 'w').close()


    class BdistDmgCommand(cx_Freeze.bdist_dmg):
        """Custom bdist_mac command."""

        def run(self):
            """Run bdist_dmg command."""
            _build_icon()
            cx_Freeze.bdist_dmg.run(self)
            # move the disk image to dist/
            _mkdir('dist/')
            if os.path.exists('dist/' + os.path.basename(self.dmgName)):
                os.unlink('dist/' + os.path.basename(self.dmgName))
            dmg_name = '{}-{}.dmg'.format(NAME, VERSION)
            os.rename(self.dmgName, dmg_name)
            shutil.move(dmg_name, 'dist/')
            wash()

        def buildDMG(self):
            # Remove DMG if it already exists
            if os.path.exists(self.dmgName):
                os.unlink(self.dmgName)
            # hdiutil with multiple -srcfolder hangs, so create a temp dir
            _prune('build/dmg')
            _mkdir('build/dmg')
            shutil.copytree(self.bundleDir, 'build/dmg/' + os.path.basename(self.bundleDir))
            # include the docs at them top level in the dmg
            shutil.copy('doc/PC-BASIC_documentation.html', 'build/dmg/Documentation.html')
            # removed application shortcuts logic as I'm not using it anyway
            # Create the dmg
            createargs = [
                'hdiutil', 'create', '-fs', 'HFSX', '-format', 'UDZO',
                self.dmgName, '-imagekey', 'zlib-level=9', '-srcfolder',
                'build/dmg', '-volname', self.volume_label,
            ]
            if os.spawnvp(os.P_WAIT, 'hdiutil', createargs) != 0:
                raise OSError('creation of the dmg failed')


    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand
    SETUP_OPTIONS['cmdclass']['bdist_mac'] = BdistMacCommand
    SETUP_OPTIONS['cmdclass']['bdist_dmg'] = BdistDmgCommand

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame', 'test',
            ],
            #'optimize': 2,
        },
        'bdist_mac': {
            'iconfile': 'resources/pcbasic.icns', 'bundle_name': '%s-%s' % (NAME, SHORT_VERSION),
        },
        'bdist_dmg': {
            # creating applications shortcut in the DMG fails somehow
            #'applications_shortcut': True,
            'volume_label': '%s-%s' % (NAME, SHORT_VERSION),
        },
    }
    SETUP_OPTIONS['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic',
            icon='resources/pcbasic.icns', copyright=COPYRIGHT
        ),
    ]

    # run the cx_Freeze setup()
    setup(**SETUP_OPTIONS)


###############################################################################
# Linux & general Python packaging

else:

    XDG_DESKTOP_ENTRY = {
        u'Name': u'PC-BASIC',
        u'GenericName': u'GW-BASIC compatible interpreter',
        u'Exec': u'/usr/local/bin/pcbasic',
        u'Terminal': u'false',
        u'Type': u'Application',
        u'Icon': u'pcbasic',
        u'Categories': u'Development;IDE;',
    }

    def _gather_resources():
        """Bring required resources together."""
        _mkdir('resources')
        with open('resources/pcbasic.desktop', 'w') as xdg_file:
            xdg_file.write(u'[Desktop Entry]\n')
            xdg_file.write(u'\n'.join(
                u'{}={}'.format(_key, _value)
                for _key, _value in XDG_DESKTOP_ENTRY.items()
            ))
            xdg_file.write(u'\n')
        _build_icon()
        shutil.copy('doc/pcbasic.1.gz', 'resources/pcbasic.1.gz')

    def bdist_rpm():
        """create .rpm package (requires fpm)"""
        wash()
        _mkdir('dist/')
        if os.path.exists('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,)):
            os.unlink('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,))
        _stamp_release()
        _gather_resources()
        _build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'rpm', '-s', 'python', '--no-auto-depends',
            '--depends=pyserial,SDL2,SDL2_gfx',
            '..'
        ), cwd='dist')
        wash()

    def bdist_deb():
        """create .deb package (requires fpm)"""
        wash()
        _mkdir('dist/')
        if os.path.exists('dist/python-pcbasic_%s_all.deb' % (VERSION,)):
            os.unlink('dist/python-pcbasic_%s_all.deb' % (VERSION,))
        _stamp_release()
        _gather_resources()
        _build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'deb', '-s', 'python', '--no-auto-depends',
            '--depends=python-serial,python-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0',
            '..'
        ), cwd='dist')
        wash()

    SETUP_OPTIONS['cmdclass'].update({
        'bdist_rpm': new_command(bdist_rpm),
        'bdist_deb': new_command(bdist_deb),
    })


    # run the setuptools setup()
    setup(**SETUP_OPTIONS)
