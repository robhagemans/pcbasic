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

import setuptools.command.build_py
import distutils.cmd


class BuildDocCommand(distutils.cmd.Command):
    """ Command to build the documentation."""

    description = 'build documentation files'
    user_options = []

    def run(self):
        """ Run build_docs command. """
        from .docsrc.prepare import build_docs
        build_docs()

    def initialize_options(self):
        """ Set default values for options. """
        pass

    def finalize_options(self):
        """ Post-process options. """
        pass


class BuildPyCommand(setuptools.command.build_py.build_py):
    """ Custom build command. """

    def run(self):
        """ Run build_py command. """
        # build_docs should not be in build but in sdist!
        #self.run_command('build_docs')
        setuptools.command.build_py.build_py.run(self)


###############################################################################
# metadata
# see https://github.com/pypa/sampleproject

from setuptools import setup, find_packages
import platform

# list of packages needed only for the present platform
platform_specific_requirements = []
if platform.system() == 'Windows':
    platform_specific_requirements.append('pywin32')


setup(
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
        'Topic :: System :: Emulators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='emulator interpreter basic retro legacy gwbasic basica pcjr tandy',
    packages=find_packages(exclude=['doc', 'test', 'docsrc', 'packaging']),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['PySDL2', 'numpy', 'pyserial', 'pexpect'] + platform_specific_requirements,

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'dev': ['lxml', 'markdown', 'pylint', 'coverage'],
        'full': ['pygame', 'pyaudio'],
    },

    package_data={
        'pcbasic': [
                '*.txt', '*.md', 'pcbasic/*.txt', 'pcbasic/data/codepages/*',
                'pcbasic/data/fonts/*', 'pcbasic/data/programs/*'],
    },
    include_package_data=True,

    entry_points={
        'console_scripts': [
            'pcbasic=pcbasic:main',
        ],
        'gui_scripts': [
            'pcbasic=pcbasic:main',
        ],

    },
    cmdclass={
        'build_docs': BuildDocCommand,
        'build_py': BuildPyCommand,
    },
)
