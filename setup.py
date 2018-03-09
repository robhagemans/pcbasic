#!/usr/bin/env python2
"""
PC-BASIC setup module.

(c) 2015--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

###############################################################################
# get descriptions and version number

from codecs import open
from os import path

# obtain metadata without importing the package (to avoid breaking setup)
with open(path.join(
        path.abspath(path.dirname(__file__)),
        'pcbasic', 'basic', 'metadata.py'), encoding='utf-8') as f:
    exec(f.read())


###############################################################################
# implement build_docs command
# see http://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setup-py.html

import setuptools.command.sdist
import distutils.cmd


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


class SDistCommand(setuptools.command.sdist.sdist):
    """ Custom sdist command. """

    def run(self):
        """ Run sdist command. """
        self.run_command('build_docs')
        setuptools.command.sdist.sdist.run(self)


###############################################################################
# metadata
# see https://github.com/pypa/sampleproject

from setuptools import setup, find_packages
#from cx_Freeze import setup, Executable
import platform

# platform-specific settings
if platform.system() == 'Windows':
    platform_specific_requirements = ['pywin32']
    console_scripts = ['pcbasic=pcbasic:winmain']
    gui_scripts = ['pcbasicw=pcbasic:main']
else:
    platform_specific_requirements = ['pexpect']
    console_scripts = ['pcbasic=pcbasic:main']
    gui_scripts = []

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
