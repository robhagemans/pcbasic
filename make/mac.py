"""
PC-BASIC - make.mac
MacOS packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import shutil
import glob
import subprocess

import cx_Freeze
from cx_Freeze import Executable

from .common import NAME, VERSION, AUTHOR, COPYRIGHT
from .common import build_icon, make_docs, prune, remove, mkdir
from .common import RESOURCE_PATH
from .freeze import SETUP_OPTIONS, SHORT_VERSION, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG
from .freeze import EXCLUDE_EXTERNAL_PACKAGES
from .freeze import build_manifest


def package():
    """Build a Mac .DMG package."""
    setup_options = SETUP_OPTIONS

    class BuildExeCommand(cx_Freeze.build_exe):
        """Custom build_exe command."""

        def run(self):
            """Run build_exe command."""
            # prepare resources
            mkdir(RESOURCE_PATH)
            build_icon()
            make_docs()
            # build the executable and library
            cx_Freeze.build_exe.run(self)
            build_dir = 'build/exe.{}/'.format(PLATFORM_TAG)
            # build_exe just includes everything inside the directory
            # so remove some stuff we don't need
            for root, _, files in os.walk(build_dir + 'lib'):
                testing = set(root.split(os.sep)) & set(('test', 'tests', 'testing', 'examples'))
                for fname in files:
                    name = os.path.join(root, fname)
                    # remove tests and examples
                    # remove windows DLLs and PYDs
                    if (testing or 'win32_' in name or name.endswith('.dll')):
                        remove(name)

    class BdistMacCommand(cx_Freeze.bdist_mac):
        """Custom bdist_mac command."""

        def run(self):
            """Run bdist_mac command."""
            cx_Freeze.bdist_mac.run(self)
            build_dir = 'build/PC-BASIC-2.0.app/Contents/MacOS/'
            # remove some files we don't need
            #for path in glob.glob('build/PC-BASIC-2.0.app/Contents/MacOS/libnpymath*'):
            #    remove(path)
            # big libs we don't need
            remove(build_dir + 'libcrypto.1.1.dylib')
            remove(build_dir + 'libssl.1.1.dylib')
            # sdl2 stuff we don't need
            prune(build_dir + 'lib/sdl2dll/dll/SDL2_mixer.framework')
            prune(build_dir + 'lib/sdl2dll/dll/SDL2_image.framework')
            prune(build_dir + 'lib/sdl2dll/dll/SDL2_ttf.framework')

        def copy_file(self, src, dst):
            # catch copy errors, these happen with relative references with funny bracketed names
            # like libnpymath.a(npy_math.o)
            try:
                cx_Freeze.bdist_mac.copy_file(self, src, dst)
            except Exception as err:
                print('ERROR: %s' % (err,))
                # create an empty file
                open(dst, 'w').close()


    class BdistDmgCommand(cx_Freeze.bdist_dmg):
        """Custom bdist_mac command."""

        def run(self):
            """Run bdist_dmg command."""
            cx_Freeze.bdist_dmg.run(self)
            # move the disk image to dist/
            mkdir('dist/')
            if os.path.exists('dist/' + os.path.basename(self.dmg_name)):
                os.unlink('dist/' + os.path.basename(self.dmg_name))
            dmg_name = '{}-{}.dmg'.format(NAME, VERSION)
            os.rename(self.dmg_name, dmg_name)
            shutil.move(dmg_name, 'dist/')
            #make_clean()

        def buildDMG(self):
            # Remove DMG if it already exists
            if os.path.exists(self.dmg_name):
                os.unlink(self.dmg_name)
            # hdiutil with multiple -srcfolder hangs, so create a temp dir
            prune('build/dmg')
            mkdir('build/dmg')
            shutil.copytree(self.bundleDir, 'build/dmg/' + os.path.basename(self.bundleDir))
            # include the docs at them top level in the dmg
            shutil.copy('build/doc/PC-BASIC_documentation.html', 'build/dmg/Documentation.html')
            # removed application shortcuts logic as I'm not using it anyway
            # Create the dmg
            createargs = [
                'hdiutil', 'create', '-fs', 'HFSX', '-format', 'UDZO',
                self.dmg_name, '-imagekey', 'zlib-level=9', '-srcfolder',
                'build/dmg', '-volname', self.volume_label,
            ]
            if os.spawnvp(os.P_WAIT, 'hdiutil', createargs) != 0:
                raise OSError('creation of the dmg failed')

    setup_options['cmdclass'] = COMMANDS
    setup_options['cmdclass']['build_exe'] = BuildExeCommand
    setup_options['cmdclass']['bdist_mac'] = BdistMacCommand
    setup_options['cmdclass']['bdist_dmg'] = BdistDmgCommand

    # cx_Freeze options
    setup_options['options'] = {
        'build_exe': {
            'excludes': EXCLUDE_EXTERNAL_PACKAGES,
            #'optimize': 2,
        },
        'bdist_mac': {
            'iconfile': 'build/resources/pcbasic.icns',
            'bundle_name': '%s-%s' % (NAME, SHORT_VERSION),
            #'codesign_identity': '-',
            #'codesign_deep': True,
        },
        'bdist_dmg': {
            # creating applications shortcut in the DMG fails somehow
            #'applications_shortcut': True,
            'volume_label': '%s-%s' % (NAME, SHORT_VERSION),
        },
    }
    setup_options['executables'] = [
        Executable(
            'run-pcbasic.py', base='Console', targetName='pcbasic',
            icon='build/resources/pcbasic.icns', copyright=COPYRIGHT
        ),
    ]

    # run the cx_Freeze setup()
    cx_Freeze.setup(script_args=['bdist_dmg'], **setup_options)
    # cx_Freeze's codesign options result in failure with "app is already signed", so trying here
    subprocess.run(['codesign', '-s', '-', '--deep', f'dist/PC-BASIC-{VERSION}.dmg'])
