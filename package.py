#!/usr/bin/env python
"""
PC-BASIC packaging script
Windows, MacOS and Linux packaging

(c) 2015--2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import shutil
import glob
import subprocess
from io import open
from distutils.util import get_platform

# get setup.py parameters
from setup import SETUP_OPTIONS, new_command, wash

# we're not setup.py and not being called by the sdist installer
# so we can import form the package if we want
from PIL import Image
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
# freezing options

SHORT_VERSION = u'.'.join(VERSION.split('.')[:2])


if CX_FREEZE and sys.platform == 'win32':

    import msilib

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            _build_icon()
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
                        print('REMOVING %s' % (name,))
                        os.remove(name)
            # remove lib dir altogether to avoid it getting copied into the msi
            # as everything in there is copied once already
            shutil.rmtree('build/lib')
            # remove c++ runtime etc
            os.remove(build_dir + 'msvcm90.dll')
            os.remove(build_dir + 'msvcp90.dll')
            # remove modules that can be left out
            for module in ('distutils', 'setuptools', 'pydoc_data'):
                try:
                    shutil.rmtree(build_dir + 'lib/%s' % module)
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

    # gui launcher
    SETUP_OPTIONS['entry_points']['gui_scripts'] = ['pcbasicw=pcbasic:main']

    # remove linux-specific files
    SETUP_OPTIONS['data_files'] = []

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


elif CX_FREEZE and sys.platform == 'darwin':

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, dirs, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for f in files:
                    name = os.path.join(root, f)
                    if (
                            # remove tests and examples
                            testing
                            # remove windows DLLs and PYDs
                            or 'win32_' in name or name.endswith('.dll')):
                        print('REMOVING %s' % (name,))
                        os.remove(name)
            # remove modules that can be left out
            for module in ('distutils', 'setuptools', 'pydoc_data'):
                try:
                    shutil.rmtree(build_dir + 'lib/%s' % module)
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
            _build_icon()
            cx_Freeze.bdist_dmg.run(self)
            # move the disk image to dist/
            try:
                os.mkdir('dist/')
            except EnvironmentError:
                pass
            if os.path.exists('dist/' + os.path.basename(self.dmgName)):
                os.unlink('dist/' + os.path.basename(self.dmgName))
            shutil.move(self.dmgName, 'dist/')
            shutil.rmtree('resources')

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

    # remove linux-specific files
    SETUP_OPTIONS['data_files'] = []

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
            'pc-basic', base='Console', targetName='pcbasic', icon='resources/pcbasic.icns',
            copyright=COPYRIGHT),
    ]


###############################################################################
# linux packaging

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
        try:
            os.mkdir('resources')
        except EnvironmentError:
            pass
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
        try:
            os.mkdir('dist/')
        except EnvironmentError:
            pass
        if os.path.exists('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,)):
            os.unlink('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,))
        _gather_resources()
        subprocess.call((
            'fpm', '-t', 'rpm', '-s', 'python', '--no-auto-depends',
            '--depends=pyserial,SDL2,SDL2_gfx',
            '../setup.py'
        ), cwd='dist')
        shutil.rmtree('resources')
        wash()

    def bdist_deb():
        """create .deb package (requires fpm)"""
        wash()
        try:
            os.mkdir('dist/')
        except EnvironmentError:
            pass
        if os.path.exists('dist/python-pcbasic_%s_all.deb' % (VERSION,)):
            os.unlink('dist/python-pcbasic_%s_all.deb' % (VERSION,))
        _gather_resources()
        subprocess.call((
            'fpm', '-t', 'deb', '-s', 'python', '--no-auto-depends',
            '--depends=python-serial,python-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0',
            '../setup.py'
        ), cwd='dist')
        shutil.rmtree('resources')
        wash()


    SETUP_OPTIONS['cmdclass'].update({
        'bdist_rpm': new_command(bdist_rpm),
        'bdist_deb': new_command(bdist_deb),
    })


###############################################################################
# run the setup

setup(**SETUP_OPTIONS)
