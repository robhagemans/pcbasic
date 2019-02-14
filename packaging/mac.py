"""
PC-BASIC - packagig.mac
MacOS packaging

(c) 2015--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import os
import shutil
import glob
import subprocess
from io import open

import cx_Freeze
from cx_Freeze import Executable, setup

from .common import wash, _build_icon, _build_manifest, _prune, _remove, _mkdir, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG


def package(SETUP_OPTIONS, NAME, AUTHOR, VERSION, SHORT_VERSION, COPYRIGHT):


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

    SETUP_OPTIONS['cmdclass'] = COMMANDS
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
    cx_Freeze.setup(script_args=['bdist_dmg'], **SETUP_OPTIONS)
