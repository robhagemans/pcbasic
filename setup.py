#!/usr/bin/env python
"""
PC-BASIC setup module.

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import platform
import shutil
import glob
import subprocess
import datetime
import json
from io import open
from setuptools.command import sdist, build_py
from subprocess import check_output, CalledProcessError

import distutils.cmd
from setuptools import find_packages, Extension


# operating in cx_Freeze mode
CX_FREEZE = set(sys.argv) & set(('bdist_msi', 'bdist_dmg', 'bdist_mac', 'build_exe'))

if CX_FREEZE:
    import cx_Freeze
    from cx_Freeze import setup, Executable
else:
    from setuptools import setup


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
exclude ISSUE_TEMPLATE.md
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


class Command(distutils.cmd.Command):
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
# metadata


SETUP_OPTIONS = {
    'name': PACKAGE,
    'version': VERSION,
    'description': DESCRIPTION,
    'long_description': LONG_DESCRIPTION,
    'url': URL,
    'author': AUTHOR,
    'author_email': EMAIL,
    'license': LICENCE,
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
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
# freezing options

shortversion = u'.'.join(VERSION.split('.')[:2])


if CX_FREEZE and sys.platform == 'win32':

    import msilib

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            cx_Freeze.build_exe.run(self)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk('build/exe.win32-2.7/lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    if (
                            # remove superfluous copies of python27.dll in lib/
                            # as there is a copy in the package root already
                            f .lower() == 'python27.dll' or f.lower() == 'msvcr90.dll' or
                            # remove tests and examples, but not for numpy (it breaks)
                            (testing and 'numpy' not in root) or
                            # we're only producing packages for win32_x86
                            'win32_x64' in name):
                        print('REMOVING %s' % (name,))
                        os.remove(name)
            # remove lib dir altogether to avoid it getting copied into the msi
            # as everything in there is copied once already
            shutil.rmtree('build/lib')
            # remove c++ runtime etc
            os.remove('build/exe.win32-2.7/msvcm90.dll')
            os.remove('build/exe.win32-2.7/msvcp90.dll')
            # remove numpy tests that can be left out (some seem needed)
            for module in [
                    'distutils', 'setuptools', 'pydoc_data', 'numpy/core/tests', 'numpy/lib/tests',
                    'numpy/f2py/tests', 'numpy/distutils', 'numpy/doc',]:
                try:
                    shutil.rmtree('build/exe.win32-2.7/lib/%s' % module)
                except EnvironmentError:
                    pass


    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand

    numversion = '.'.join(v for v in VERSION.encode('ascii').split('.') if v.isdigit())
    UPGRADE_CODE = '{714d23a9-aa94-4b17-87a5-90e72d0c5b8f}'
    PRODUCT_CODE = msilib.gen_uuid()

    # these must be bytes for cx_Freeze bdist_msi
    SETUP_OPTIONS['name'] = NAME.encode('ascii')
    SETUP_OPTIONS['author'] = AUTHOR.encode('ascii')
    SETUP_OPTIONS['version'] = numversion

    # compile separately, as they end up in the wrong place anyway
    SETUP_OPTIONS['ext_modules'] = []

    directory_table = [
        (
            'StartMenuFolder',
            'TARGETDIR',
            '.',
        ),
        (
            'MyProgramMenu',
            'StartMenuFolder',
            'PCBASI~1|PC-BASIC 2.0',
        ),
    ]
    # https://stackoverflow.com/questions/15734703/use-cx-freeze-to-create-an-msi-that-adds-a-shortcut-to-the-desktop#15736406
    shortcut_table = [
        (
            'ProgramShortcut',        # Shortcut
            'MyProgramMenu',          # Directory_
            'PC-BASIC %s' % VERSION,  # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]pcbasicw.exe',# Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'PersonalFolder'          # WkDir
        ),
        (
            'DocShortcut',            # Shortcut
            'MyProgramMenu',          # Directory_
            'Documentation',          # Name
            'TARGETDIR',              # Component_
            '[TARGETDIR]PC-BASIC_documentation.html',# Target
            None,                     # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            'TARGETDIR'               # WkDir
        ),
        (
            'UninstallShortcut',      # Shortcut
            'MyProgramMenu',          # Directory_
            'Uninstall',              # Name
            'TARGETDIR',              # Component_
            '[SystemFolder]msiexec.exe', # Target
            '/x %s' % PRODUCT_CODE,           # Arguments
            None,                     # Description
            None,                     # Hotkey
            None,                     # Icon
            None,                     # IconIndex
            None,                     # ShowCmd
            # PersonalFolder is My Documents, use as Start In folder
            'TARGETDIR'               # WkDir
        ),
    ]
    msi_data = {
        'Directory': directory_table,
        'Shortcut': shortcut_table,
        'Icon': [('PC-BASIC-Icon', msilib.Binary('icons/pcbasic.ico')),],
        'Property': [('ARPPRODUCTICON', 'PC-BASIC-Icon'),],
    }

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['numpy', 'pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame',
                'pywin', 'win32com', 'test',
            ],
            'include_files': ['doc/PC-BASIC_documentation.html'],
            'include_msvcr': True,
            #'optimize': 2,
        },
        'bdist_msi': {
            'data': msi_data,
            # add console entry points to PATH
            'add_to_path': True,
            # enforce removal of old versions
            'upgrade_code': UPGRADE_CODE,
            'product_code': PRODUCT_CODE,
            'initial_target_dir': 'c:\\Program Files\\%s %s' % (NAME, shortversion),
        },
    }

    SETUP_OPTIONS['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic.exe', icon='icons/pcbasic.ico',
            copyright=COPYRIGHT),
        Executable(
            'pc-basic', base='Win32GUI', targetName='pcbasicw.exe', icon='icons/pcbasic.ico',
            #shortcutName='PC-BASIC %s' % VERSION, shortcutDir='MyProgramMenu',
            copyright=COPYRIGHT),
    ]


elif CX_FREEZE and sys.platform == 'darwin':

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            cx_Freeze.build_exe.run(self)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk('build/exe.macosx-10.13-x86_64-2.7/lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    if (
                            # remove tests and examples, but not for numpy (it breaks)
                            (testing and 'numpy' not in root) or
                            # remove windows DLLs and PYDs
                            'win32_' in name):
                        print('REMOVING %s' % (name,))
                        os.remove(name)
            # remove modules that can be left out (some numpy tests seem needed)
            for module in [
                    'distutils', 'setuptools', 'pydoc_data', 'numpy/core/tests', 'numpy/lib/tests',
                    'numpy/f2py/tests', 'numpy/distutils', 'numpy/doc',]:
                try:
                    shutil.rmtree('build/exe.macosx-10.13-x86_64-2.7/lib/%s' % module)
                except EnvironmentError:
                    pass


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
            os.remove('build/PC-BASIC-2.0.app/Contents/MacOS/libSDL2.dylib')
            for path in glob.glob('build/PC-BASIC-2.0.app/Contents/MacOS/libnpymath*'):
                os.remove(path)


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
            cx_Freeze.bdist_dmg.run(self)
            # move the disk image to dist/
            try:
                os.mkdir('dist/')
            except EnvironmentError:
                pass
            if os.path.exists('dist/' + os.path.basename(self.dmgName)):
                os.unlink('dist/' + os.path.basename(self.dmgName))
            shutil.move(self.dmgName, 'dist/')

        def buildDMG(self):
            # Remove DMG if it already exists
            if os.path.exists(self.dmgName):
                os.unlink(self.dmgName)

            # hdiutil with multiple -srcfolder hangs, so create a temp dir
            try:
                shutil.rmtree('build/dmg')
            except EnvironmentError as e:
                print(e)
            try:
                os.mkdir('build/dmg')
            except EnvironmentError as e:
                print(e)
            shutil.copytree(self.bundleDir, 'build/dmg/' + os.path.basename(self.bundleDir))
            # include the docs at them top level in the dmg
            shutil.copy('doc/PC-BASIC_documentation.html', 'build/dmg/Documentation.html')

            createargs = [
                'hdiutil', 'create', '-fs', 'HFSX', '-format', 'UDZO',
                self.dmgName, '-imagekey', 'zlib-level=9', '-srcfolder',
                'build/dmg', '-volname', self.volume_label,
            ]
            # removed application shortcuts logic as I'm not using it anyway

            # Create the dmg
            if os.spawnvp(os.P_WAIT, 'hdiutil', createargs) != 0:
                raise OSError('creation of the dmg failed')


    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand
    SETUP_OPTIONS['cmdclass']['bdist_mac'] = BdistMacCommand
    SETUP_OPTIONS['cmdclass']['bdist_dmg'] = BdistDmgCommand

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['numpy', 'pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame', 'test',
            ],
            #'optimize': 2,
        },
        'bdist_mac': {
            'iconfile': 'icons/pcbasic.icns', 'bundle_name': '%s-%s' % (NAME, shortversion),
        },
        'bdist_dmg': {
            # creating applications shortcut in the DMG fails somehow
            #'applications_shortcut': True,
            'volume_label': '%s-%s' % (NAME, shortversion),
        },
    }
    SETUP_OPTIONS['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic', icon='icons/pcbasic.icns',
            copyright=COPYRIGHT),
    ]

###############################################################################
# linux packaging


class BdistRpmCommand(Command):
    """Command to create a .rpm package."""

    description = 'create .rpm package (requires fpm)'

    def run(self):
        """Create .rpm package."""
        try:
            os.mkdir('dist/')
        except EnvironmentError:
            pass
        if os.path.exists('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,)):
            os.unlink('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,))
        os.chdir('dist')
        subprocess.call((
            'fpm', '-t', 'rpm', '-s', 'python', '--no-auto-depends',
            '--prefix=/usr/local/lib/python2.7/site-packages/',
            '--depends=numpy,pyserial,SDL2,SDL2_gfx', '..'
        ))


class BdistDebCommand(Command):
    """Command to create a .deb package."""

    description = 'create .deb package (requires fpm)'

    def run(self):
        """Create .deb package."""
        try:
            os.mkdir('dist/')
        except EnvironmentError:
            pass
        if os.path.exists('dist/python-pcbasic_%s_all.deb' % (VERSION,)):
            os.unlink('dist/python-pcbasic_%s_all.deb' % (VERSION,))
        os.chdir('dist')
        subprocess.call((
            'fpm', '-t', 'deb', '-s', 'python', '--no-auto-depends',
            '--prefix=/usr/local/lib/python2.7/site-packages/',
            '--depends=python-numpy,python-serial,python-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0',
            '..'
        ))


SETUP_OPTIONS['cmdclass']['bdist_rpm'] = BdistRpmCommand
SETUP_OPTIONS['cmdclass']['bdist_deb'] = BdistDebCommand


###############################################################################
# run the setup

setup(**SETUP_OPTIONS)
