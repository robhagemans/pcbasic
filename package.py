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

    import msilib

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            _build_icon()
            # only include 32-bit DLLs
            _build_manifest(INCLUDE_FILES + ('pcbasic/lib/win32_x86/*',), EXCLUDE_FILES)
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    if (
                            # remove superfluous copies of python27.dll in lib/
                            # as there is a copy in the package root already
                            f.lower() == 'python27.dll' or f.lower() == 'msvcr90.dll'
                            # remove tests and examples
                            or testing
                            # we're only producing packages for win32_x86
                            or 'win32_x64' in name or name.endswith('.dylib')
                        ):
                        _remove(name)
            # remove lib dir altogether to avoid it getting copied into the msi
            # as everything in there is copied once already
            _prune('build/lib')
            # remove c++ runtime etc
            _remove(build_dir + 'msvcm90.dll')
            _remove(build_dir + 'msvcp90.dll')
            # remove modules that can be left out
            for module in ('distutils', 'setuptools', 'pydoc_data'):
                _prune(build_dir + 'lib/%s' % module)


    class BdistMsiCommand(cx_Freeze.bdist_msi):
        """Custom bdist_msi command."""

        def run(self):
            """Run build_msi command."""
            name = '{}-{}'.format(NAME, VERSION)
            _remove('dist/{}.msi'.format(name))
            cx_Freeze.bdist_msi.run(self)
            # close the database file so we can rename the file
            del self.db
            os.rename('dist/{}-win32.msi'.format(name), 'dist/{}.msi'.format(name))
            wash()

        # mostly copy-paste from cxfreeze
        def add_config(self, fullname):
            # PATH needs uac??
            if self.add_to_path:
                msilib.add_data(self.db, 'Environment',
                        [("E_PATH", "=-*Path", r"[~];[TARGETDIR]", "TARGETDIR")])
            if self.directories:
                msilib.add_data(self.db, "Directory", self.directories)
            #if self.environment_variables:
            #    msilib.add_data(self.db, "Environment", self.environment_variables)
            msilib.add_data(self.db, 'CustomAction',
                    [("A_SET_TARGET_DIR", 256 + 51, "TARGETDIR",
                            self.initial_target_dir)])
            msilib.add_data(self.db, 'InstallExecuteSequence',
                    [("A_SET_TARGET_DIR", 'TARGETDIR=""', 401)])
            msilib.add_data(self.db, 'InstallUISequence',
                [("PrepareDlg", None, 140),
                # this is new
                ("WhichUsersDlg", None, 123),
                ("A_SET_TARGET_DIR", 'TARGETDIR=""', 401),
                ("SelectDirectoryDlg", "not Installed", 1230),
                ("MaintenanceTypeDlg",
                "Installed and not Resume and not Preselected", 1250),
                ("ProgressDlg", None, 1280)
            ])
            for index, executable in enumerate(self.distribution.executables):
                if executable.shortcutName is not None \
                        and executable.shortcutDir is not None:
                    baseName = os.path.basename(executable.targetName)
                    msilib.add_data(self.db, "Shortcut",
                            [("S_APP_%s" % index, executable.shortcutDir,
                                    executable.shortcutName, "TARGETDIR",
                                    "[TARGETDIR]%s" % baseName, None, None, None,
                                    None, None, None, None)])
            for tableName, data in self.data.items():
                msilib.add_data(self.db, tableName, data)

        # mostly copy-paste from cxfreeze
        def add_properties(self):
            metadata = self.distribution.metadata
            props = [
                    ('DistVersion', metadata.get_version()),
                    ('DefaultUIFont', 'DlgFont8'),
                    ('ErrorDialog', 'ErrorDlg'),
                    ('Progress1', 'Install'),
                    ('Progress2', 'installs'),
                    ('MaintenanceForm_Action', 'Repair'),
                    ('ALLUSERS', '2') #'2'
            ]
            email = metadata.author_email or metadata.maintainer_email
            if email:
                props.append(("ARPCONTACT", email))
            if metadata.url:
                props.append(("ARPURLINFOABOUT", metadata.url))
            if self.upgrade_code is not None:
                props.append(("UpgradeCode", self.upgrade_code))
            #if self.install_icon:
            #    props.append(('ARPPRODUCTICON', 'InstallIcon'))
            msilib.add_data(self.db, 'Property', props)
            #if self.install_icon:
            #    msilib.add_data(self.db, "Icon", [("InstallIcon", msilib.Binary(self.install_icon))])

        def add_ui(self):
            # dialog from cpython 2.7
            # https://svn.python.org/projects/python/trunk/Tools/msi/msi.py
            whichusers = distutils.command.bdist_msi.PyDialog(
                self.db, "WhichUsersDlg", self.x, self.y, self.width, self.height,
                self.modal, self.title, "AdminInstall", "Next", "Cancel"
            )
            whichusers.title(
                "Select whether to install [ProductName] for all users of this computer."
            )
            # A radio group with two options: allusers, justme
            g = whichusers.radiogroup(
                "AdminInstall", 135, 60, 235, 80, 3, "WhichUsers", "", "Next"
            )
            g.condition("Disable", "VersionNT=600") # Not available on Vista and Windows 2008
            g.add("ALL", 0, 5, 150, 20, "Install for all users")
            g.add("JUSTME", 0, 25, 235, 20, "Install just for me")

            whichusers.back("Back", None, active=0)

            c = whichusers.next("Next >", "Cancel")
            # SetProperty events
            # https://docs.microsoft.com/en-us/windows/desktop/Msi/setproperty-controlevent
            c.event("[MSIINSTALLPERUSER]", "{}", 'WhichUsers="ALL"', 1)
            c.event("[MSIINSTALLPERUSER]", "1", 'WhichUsers="JUSTME"', 1)
            #FIXME: set to the official location %LOCALAPPDATA%\Programs
            c.event("[TARGETDIR]", "[%%USERPROFILE]\\%s %s" % (NAME, SHORT_VERSION), 'WhichUsers="JUSTME"', 1)
            c.event("EndDialog", "Return", 3)

            c = whichusers.cancel("Cancel", "AdminInstall")
            c.event("SpawnDialog", "CancelDlg")

            cx_Freeze.bdist_msi.add_ui(self)



    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand
    SETUP_OPTIONS['cmdclass']['bdist_msi'] = BdistMsiCommand

    numversion = '.'.join(v for v in VERSION.encode('ascii').split('.') if v.isdigit())
    UPGRADE_CODE = '{714d23a9-aa94-4b17-87a5-90e72d0c5b8f}'
    PRODUCT_CODE = msilib.gen_uuid()

    # these must be bytes for cx_Freeze bdist_msi
    SETUP_OPTIONS['name'] = NAME.encode('ascii')
    SETUP_OPTIONS['author'] = AUTHOR.encode('ascii')
    SETUP_OPTIONS['version'] = numversion

    # compile separately, as they end up in the wrong place anyway
    SETUP_OPTIONS['ext_modules'] = []

    # gui launcher
    SETUP_OPTIONS['entry_points']['gui_scripts'] = ['pcbasicw=pcbasic:main']

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
        'Icon': [('PC-BASIC-Icon', msilib.Binary('resources/pcbasic.ico')),],
        'Property': [('ARPPRODUCTICON', 'PC-BASIC-Icon'),],
    }

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['pkg_resources._vendor'],
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
            'initial_target_dir': 'c:\\Program Files\\%s %s' % (NAME, SHORT_VERSION),
        },
    }

    SETUP_OPTIONS['executables'] = [
        Executable(
            'pc-basic', base='Console', targetName='pcbasic.exe', icon='resources/pcbasic.ico',
            copyright=COPYRIGHT),
        Executable(
            'pc-basic', base='Win32GUI', targetName='pcbasicw.exe', icon='resources/pcbasic.ico',
            #shortcutName='PC-BASIC %s' % VERSION, shortcutDir='MyProgramMenu',
            copyright=COPYRIGHT),
    ]


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


###############################################################################
# Linux

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


###############################################################################
# run the setup

setup(**SETUP_OPTIONS)
