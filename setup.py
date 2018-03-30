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
from setuptools import setup, find_packages, Extension
#from cx_Freeze import setup, Executable


# this is the base MANIFEST.in
# but I need it to change for different platforms/commands
DUNMANIFESTIN = """
include *.md
include GPL3.txt
include doc/*
include pcbasic/data/USAGE.txt
include pcbasic/data/*/*
"""
#
HERE = os.path.abspath(os.path.dirname(__file__))


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


setup(

    # metadata

    name='pcbasic',
    version=VERSION,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    url=URL,
    author=AUTHOR,
    author_email=EMAIL,
    license=LICENCE,

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Topic :: System :: Emulators',
        'Topic :: Software Development :: Interpreters',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='emulator interpreter basic retro legacy gwbasic basica pcjr tandy',

    # contents

    packages=find_packages(exclude=['doc', 'test', 'docsrc', 'packaging']),

    # rule of thumb for sdist: package_data specifies what gets *installed*,
    # but manifest specifies what gets *included* in the archive in the first place
    package_data={
        'pcbasic': [
                '*.txt', '*.md', 'pcbasic/*.txt', 'pcbasic/data/codepages/*',
                'pcbasic/data/fonts/*', 'pcbasic/data/programs/*',
                'pcbasic/lib/*',
            ],
    },

    ext_modules=ext_modules,

    include_package_data=True,

    # requirements

    # need a Python-2 that's 2.7.12 or better
    python_requires='~=2.7.12',

    install_requires=['PySDL2', 'numpy', 'pyserial'] + platform_specific_requirements,

    # use e.g. pip install -e .[dev,full]
    extras_require={
        'dev': ['lxml', 'markdown', 'pylint', 'coverage'],
        'full': ['pygame', 'pyaudio'],
    },

    # launchers

    entry_points={
        'console_scripts': console_scripts,
        'gui_scripts': gui_scripts,
    },

    # setup commands

    cmdclass={
        'build_docs': BuildDocCommand,
        'sdist': SDistCommand,
        'sdist_dev': SDistDevCommand,
        'build_py': BuildPyCommand,
    },

    # cx_Freeze options
    #
    # options={'build_exe': {
    #             'packages': ['numpy'],
    #             'excludes': ['tkinter', 'tcltk', 'nose', 'PIL', 'PyQt4', 'scipy', 'pygame'],
    #             #'optimize': 2,
    #             },
    #         },
    # executables = [Executable('run.py', base=None)],
)
