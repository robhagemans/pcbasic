#!/usr/bin/env python2
"""
PC-BASIC setup module.

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import platform
from codecs import open
from setuptools.command import sdist, build_py

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
DUNMANIFESTIN = """
include *.md
include GPL3.txt
include doc/*
include pcbasic/data/USAGE.txt
include pcbasic/data/*/*
"""


###############################################################################
# get descriptions and version number

# obtain metadata without importing the package (to avoid breaking setup)
with open(os.path.join(HERE, 'pcbasic', 'metadata.py'), encoding='utf-8') as f:
    exec(f.read())


###############################################################################
# implement build_docs command
# see http://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setup-py.html

class BuildDocCommand(distutils.cmd.Command):
    """ Command to build the documentation."""

    description = 'build documentation files'
    user_options = []

    def run(self):
        """ Run build_docs command. """
        from docsrc.prepare import build_docs
        build_docs()

    def initialize_options(self):
        """ Set default values for options. """
        pass

    def finalize_options(self):
        """ Post-process options. """
        pass


class SDistCommand(sdist.sdist):
    """Custom sdist command."""

    def run(self):
        """Run sdist command."""
        with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
            f.write(DUNMANIFESTIN)
            f.write(
                'include pcbasic/lib/README.md\n'
                'include pcbasic/compat/*.c\n'
                'prune test\n'
            )
        self.run_command('build_docs')
        sdist.sdist.run(self)
        os.remove(os.path.join(HERE, 'MANIFEST.in'))


class SDistDevCommand(sdist.sdist):
    """Custom sdist_dev command."""

    def run(self):
        """Run sdist_dev command."""
        with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
            f.write(DUNMANIFESTIN)
            f.write(
                'include pcbasic/lib/*\n'
                'include pcbasic/lib/*/*\n'
                'include pcbasic/compat/*.c\n'
                'recursive-include test *'
            )
        self.run_command('build_docs')
        sdist.sdist.run(self)
        os.remove(os.path.join(HERE, 'MANIFEST.in'))


class BuildPyCommand(build_py.build_py):
    """Custom build_py command."""

    def run(self):
        """Run build_py command."""
        with open(os.path.join(HERE, 'MANIFEST.in'), 'w') as f:
            f.write(DUNMANIFESTIN)
            f.write('prune test\n')
            # include DLLs on Windows
            if sys.platform == 'win32':
                if platform.architecture()[0] == '64bit':
                    f.write('include pcbasic/lib/win32_x64/*.dll\n')
                else:
                    f.write('include pcbasic/lib/win32_x86/*.dll\n')
        build_py.build_py.run(self)
        os.remove(os.path.join(HERE, 'MANIFEST.in'))


###############################################################################
# metadata
# see https://github.com/pypa/sampleproject

# platform-specific settings
if sys.platform == 'win32':
    platform_specific_requirements = []
    console_scripts = ['pcbasic=pcbasic:main']
    gui_scripts = ['pcbasicw=pcbasic:main']
    # use different names for 32- and 64-bit pyds to allow them to stay side-by-side in place
    if platform.architecture()[0] == '32bit':
        console_name = 'win32_x86_console'
    else:
        console_name = 'win32_x64_console'
    ext_modules = [Extension('pcbasic.compat.' + console_name, ['pcbasic/compat/win32_console.c'])]
else:
    platform_specific_requirements = []
    console_scripts = ['pcbasic=pcbasic:main']
    gui_scripts = []
    ext_modules = []


SETUP_OPTIONS = {
    'name': 'pcbasic',
    'version': VERSION,
    'description': DESCRIPTION,
    'long_description': LONG_DESCRIPTION,
    'url': URL,
    'author': AUTHOR,
    'author_email': EMAIL,
    'license': LICENCE,

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Topic :: System :: Emulators',
        'Topic :: Software Development :: Interpreters',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
    ],
    'keywords': 'emulator interpreter basic retro legacy gwbasic basica pcjr tandy',

    # contents
    'packages': find_packages(exclude=['doc', 'test', 'docsrc', 'icons']),
    # rule of thumb for sdist: package_data specifies what gets *installed*,
    # but manifest specifies what gets *included* in the archive in the first place
    'package_data': {
        'pcbasic': [
                '*.txt', '*.md', 'pcbasic/*.txt', 'pcbasic/data/codepages/*',
                'pcbasic/data/fonts/*', 'pcbasic/data/programs/*',
                'pcbasic/lib/*',
            ],
    },
    'ext_modules': ext_modules,
    'include_package_data': True,

    # requirements
    # need a Python-2 that's 2.7.12 or better
    'python_requires': '~=2.7.12',
    'install_requires': ['numpy', 'pyserial', 'pyparallel'] + platform_specific_requirements,
    # use e.g. pip install -e .[dev,full]
    'extras_require': {
        'dev': ['lxml', 'markdown', 'pylint', 'coverage', 'cx_Freeze'],
        'full': ['pygame', 'pyaudio'],
    },

    # launchers
    'entry_points': {
        'console_scripts': console_scripts,
        'gui_scripts': gui_scripts,
    },

    # setup commands
    'cmdclass': {
        'build_docs': BuildDocCommand,
        'sdist': SDistCommand,
        'sdist_dev': SDistDevCommand,
        'build_py': BuildPyCommand,
    },
}

###############################################################################
# freezing options

shortversion = '.'.join(VERSION.encode('ascii').split('.')[:2])


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
                            f == 'python27.dll' or
                            # remove tests and examples, but not for numpy (it breaks)
                            (testing and 'numpy' not in root) or
                            # we're only producing packages for win32_x86
                            'win32_x64' in name):
                        print 'REMOVING %s' % (name,)
                        os.remove(name)


    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand

    numversion = '.'.join(v for v in VERSION.encode('ascii').split('.') if v.isdigit())
    UPGRADE_CODE = '{714d23a9-aa94-4b17-87a5-90e72d0c5b8f}'
    PRODUCT_CODE = msilib.gen_uuid()

    # these must be bytes for cx_Freeze bdist_msi
    SETUP_OPTIONS['name'] = NAME.encode('ascii')
    SETUP_OPTIONS['author'] = AUTHOR.encode('ascii')
    SETUP_OPTIONS['version'] = numversion


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
            #'optimize': 2,
        },
        'bdist_msi': {
            'data': msi_data,
            # add console entry points to PATH
            'add_to_path': True,
            # enforce removal of old versions
            'upgrade_code': UPGRADE_CODE,
            'product_code': PRODUCT_CODE,
            'initial_target_dir': 'c:\\Program Files\\%s %s' % (NAME.encode('ascii'), shortversion),
        },
    }

    SETUP_OPTIONS['executables'] = [
        Executable(
            'run.py', base='Console', targetName='pcbasic.exe', icon='icons/pcbasic.ico',
            copyright=COPYRIGHT),
        Executable(
            'run.py', base='Win32GUI', targetName='pcbasicw.exe', icon='icons/pcbasic.ico',
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
                        print 'REMOVING %s' % (name,)
                        os.remove(name)



    class BdistMacCommand(cx_Freeze.bdist_mac):
        """Custom bdist_mac command."""

        def copy_file(self, src, dst):
            # catch copy errors, these happen with relative references with funny bracketed names
            # like libnpymath.a(npy_math.o)
            try:
                cx_Freeze.bdist_mac.copy_file(self, src, dst)
            except Exception as e:
                print 'ERROR: %s' % (e,)
                # create an empty file
                open(dst, 'w').close()


    SETUP_OPTIONS['cmdclass']['build_exe'] = BuildExeCommand
    SETUP_OPTIONS['cmdclass']['bdist_mac'] = BdistMacCommand

    # cx_Freeze options
    SETUP_OPTIONS['options'] = {
        'build_exe': {
            'packages': ['numpy', 'pkg_resources._vendor'],
            'excludes': [
                'Tkinter', '_tkinter', 'PIL', 'PyQt4', 'scipy', 'pygame', 'test',
            ],
            'include_files': ['doc/PC-BASIC_documentation.html'],
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
            'run.py', base='Console', targetName='pcbasic', icon='icons/pcbasic.icns',
            copyright=COPYRIGHT),
    ]


###############################################################################
# run the setup

setup(**SETUP_OPTIONS)
