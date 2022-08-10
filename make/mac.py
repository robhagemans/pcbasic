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
from .common import build_icon, make_docs, prune, remove, mkdir, make_ready
from .common import RESOURCE_PATH
from .freeze import SETUP_OPTIONS, SHORT_VERSION, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG
from .freeze import EXCLUDE_EXTERNAL_PACKAGES


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
            exclude = set(root.split(os.sep)) & set(
                ('Headers', 'test', 'tests', 'testing', 'examples')
            )
            for fname in files:
                name = os.path.join(root, fname)
                # remove tests and examples
                # remove windows DLLs and PYDs
                if (exclude or 'win32_' in name or name.endswith('.dll')):
                    remove(name)

class BdistMacCommand(cx_Freeze.bdist_mac):
    """Custom bdist_mac command."""

    def run(self):
        """Run bdist_mac command."""
        cx_Freeze.bdist_mac.run(self)
        #'build/PC-BASIC-2.0.app/Contents/MacOS/'
        build_dir = self.bundle_dir + '/Contents/MacOS/'
        # big libs we don't need
        remove(build_dir + 'libcrypto.1.1.dylib')
        remove(build_dir + 'libssl.1.1.dylib')
        # sdl2 stuff we don't need
        prune(build_dir + 'lib/sdl2dll/dll/SDL2_mixer.framework')
        prune(build_dir + 'lib/sdl2dll/dll/SDL2_image.framework')
        prune(build_dir + 'lib/sdl2dll/dll/SDL2_ttf.framework')
        # fix sdl symlinks, or codesign will bork
        cwd = os.getcwd()
        os.chdir(build_dir + 'lib/sdl2dll/dll/SDL2.framework/Versions/')
        os.symlink('A', 'Current')
        os.chdir('..')
        os.symlink('Versions/Current/SDL2', 'SDL2')
        os.symlink('Versions/Current/Resources', 'Resources')
        #os.symlink('Versions/Current/Headers', 'Headers')
        os.chdir(cwd)
        os.chdir(build_dir + 'lib/sdl2dll/dll/SDL2_gfx.framework/Versions/')
        os.symlink('A', 'Current')
        os.chdir('..')
        os.symlink('Versions/Current/SDL2_gfx', 'SDL2_gfx')
        os.symlink('Versions/Current/Resources', 'Resources')
        #os.symlink('Versions/Current/Headers', 'Headers')
        os.chdir(cwd)
        # codesign the app
        print('>>> ad hoc code signing ', self.bundle_dir)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', self.bundle_dir])

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
        dmg_name = '{}-{}.dmg'.format(NAME, VERSION)
        if os.path.exists('dist/' + os.path.basename(dmg_name)):
            os.unlink('dist/' + os.path.basename(dmg_name))
        os.rename(self.dmg_name, dmg_name)
        shutil.move(dmg_name, 'dist/')
        #make_clean()

    def build_dmg(self):
        # from cx_Freeze 6.11.1 source

        # Remove DMG if it already exists
        if os.path.exists(self.dmg_name):
            os.unlink(self.dmg_name)

        # Make dist folder
        self.dist_dir = os.path.join(self.build_dir, "dist")
        if os.path.exists(self.dist_dir):
            shutil.rmtree(self.dist_dir)
        self.mkpath(self.dist_dir)

        # Copy App Bundle
        dest_dir = os.path.join(
            self.dist_dir, os.path.basename(self.bundle_dir)
        )
        #self.copy_tree(self.bundle_dir, dest_dir)
        shutil.copytree(self.bundle_dir, dest_dir, symlinks=True)

        # seems we have to sign *again*, for some reason
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', dest_dir])

        ### added
        # include the docs at them top level in the dmg
        shutil.copy('build/doc/PC-BASIC_documentation.html', self.dist_dir)
        ###

        createargs = [
            "hdiutil",
            "create",
        ]
        if self.silent:
            createargs += ["-quiet"]
        createargs += [
            "-fs",
            "HFSX",
            "-format",
            "UDZO",
            self.dmg_name,
            "-imagekey",
            "zlib-level=9",
            "-srcfolder",
            self.dist_dir,
            "-volname",
            self.volume_label,
        ]

        if self.applications_shortcut:
            apps_folder_link = os.path.join(self.dist_dir, "Applications")
            os.symlink(
                "/Applications", apps_folder_link, target_is_directory=True
            )

        # Create the dmg
        if subprocess.call(createargs) != 0:
            raise OSError("creation of the dmg failed")


def package():
    """Build a Mac .DMG package."""
    setup_options = SETUP_OPTIONS
    make_ready()

    setup_options['cmdclass'] = dict(
        build_exe=BuildExeCommand,
        bdist_mac=BdistMacCommand,
        bdist_dmg=BdistDmgCommand,
    )

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
    #subprocess.run(['codesign', '-s', '-', '--deep', f'dist/PC-BASIC-{VERSION}.dmg'])
