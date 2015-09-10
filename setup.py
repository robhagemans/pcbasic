"""
PC-BASIC setup module.

(c) 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

###############################################################################
# get descriptions and version number

from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'docsrc', 'description.txt'), encoding='utf-8') as f:
    long_description = f.read()

with open(path.join(here, 'docsrc', 'tagline.txt'), encoding='utf-8') as f:
    description = f.read()

with open(path.join(here, 'pcbasic', 'data', 'version.txt'), encoding='utf-8') as f:
    version_string = f.read()


###############################################################################
# implement build_docs command
# see http://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setup-py.html

import distutils.cmd
import setuptools.command.build_py

import prepare

class BuildDocCommand(distutils.cmd.Command):
    """ Command to build the documentation."""

    description = 'build documentation files'
    user_options = []

    def run(self):
        """ Run build_docs command. """
        prepare.build_docs()

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
        self.run_command('build_docs')
        setuptools.command.build_py.build_py.run(self)


###############################################################################
# metadata
# see https://github.com/pypa/sampleproject

from setuptools import setup, find_packages

setup(
    name='pcbasic',
    version=version_string,
    description=description,
    long_description=long_description,
    url='http://pc-basic.org',
    author='Rob Hagemans',
    author_email='robhagemans@yahoo.co.uk',
    license='GPLv3',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Topic :: System :: Emulators',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='emulator interpreter basic retro legacy gwbasic basica pcjr tandy basicode',
    packages=find_packages(exclude=['doc', 'test', 'docsrc', 'packaging', 'patches']),

    # List run-time dependencies here.  These will be installed by pip when
    # your project is installed. For an analysis of "install_requires" vs pip's
    # requirements files see:
    # https://packaging.python.org/en/latest/requirements.html
    install_requires=['pygame', 'numpy', 'pyxdg', 'pyserial', 'pexpect'],

    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    #extras_require={
    #    'dev': ['check-manifest'],
    #    'test': ['coverage'],
    #},

    package_data={
        'pcbasic': ['data/*', 'encoding/*',
                    'font/*'],
    },
    entry_points={
        'console_scripts': [
            'pcbasic=pcbasic.__main__:main',
        ],
        'gui_scripts': [
            'pcbasic=pcbasic.__main__:main',
        ],

    },
    cmdclass={
        'build_docs': BuildDocCommand,
        'build_py': BuildPyCommand,
    },
)
