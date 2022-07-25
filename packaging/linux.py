"""
PC-BASIC - packaging.linux
Linux packaging

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import shutil
import subprocess
from io import open

from setuptools import setup

from .common import wash, new_command, build_icon, build_docs, build_manifest, stamp_release, mkdir, remove
from .common import HERE, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES
from .common import AUTHOR, VERSION


XDG_DESKTOP_ENTRY = {
    u'Name': u'PC-BASIC',
    u'GenericName': u'GW-BASIC compatible interpreter',
    u'Exec': u'/usr/local/bin/pcbasic',
    u'Terminal': u'false',
    u'Type': u'Application',
    u'Icon': u'pcbasic',
    u'Categories': u'Development;IDE;',
}

SETUP_CFG = os.path.join(HERE, 'setup.cfg')


def package(**setup_options):
    """Build Linux .DEB and .RPM packages."""

    def _gather_resources():
        """Bring required resources together."""
        mkdir('resources')
        with open('resources/pcbasic.desktop', 'w') as xdg_file:
            xdg_file.write(u'[Desktop Entry]\n')
            xdg_file.write(u'\n'.join(
                u'{}={}'.format(_key, _value)
                for _key, _value in XDG_DESKTOP_ENTRY.items()
            ))
            xdg_file.write(u'\n')
        build_icon()
        build_docs()
        shutil.copy('doc/pcbasic.1.gz', 'resources/pcbasic.1.gz')
        # prepare a setup.cfg in the root
        with open(SETUP_CFG, 'w') as setup_cfg:
            setup_cfg.write(u'\n'.join((
                u'[metadata]',
                u'version = {}'.format(VERSION),
                u'author = {}'.format(AUTHOR),
                u'\n'.join((
                    u'{} = {}'.format(_key, _value)
                    for _key, _value in setup_options.items()
                    if _key in (
                        u'url', u'author_email', u'license', u'description', u'long_description',
                        u'keywords', u'classifiers'
                    )
                )),
                u'',
                #u'[options]',
                #u'include_package_data = True',
                #u'packages = {}'.format(u','.join(packages),
                #u'',
                #u'[options.entry_points]',
                #u'console_scripts = pcbasic=pcbasic:main',
                #u'',
            )))
            # data_files is deprecated / discouraged, but not clear how else to do this
            # so that desktop files get picked up by setup.py install and hence by fpm
            setup_cfg.write('\n'.join([
                u'[options.data_files]',
                u'/usr/local/share/man/man1 = resources/pcbasic.1.gz',
                u'/usr/local/share/applications = resources/pcbasic.desktop',
                u'/usr/local/share/icons = resources/pcbasic.png',
                u''
            ]))


    def bdist_rpm():
        """create .rpm package (requires fpm)"""
        wash()
        mkdir('dist/')
        if os.path.exists('dist/python3-pcbasic-%s-1.noarch.rpm' % (VERSION,)):
            os.unlink('dist/python3-pcbasic-%s-1.noarch.rpm' % (VERSION,))
        stamp_release()
        _gather_resources()
        build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'rpm', '-s',
            'python', '--verbose', '--no-auto-depends',
            '--python-scripts-executable', '/usr/bin/env python3',
            '--python-bin', 'python3',
            '--python-package-name-prefix', 'python3',
            '--depends=pyserial,SDL2,SDL2_gfx',
            '..'
        ), cwd='dist')
        wash()
        remove(SETUP_CFG)

    def bdist_deb():
        """create .deb package (requires fpm)"""
        wash()
        mkdir('dist/')
        if os.path.exists('dist/python3-pcbasic_%s_all.deb' % (VERSION,)):
            os.unlink('dist/python3-pcbasic_%s_all.deb' % (VERSION,))
        stamp_release()
        _gather_resources()
        # for some reason, python files in tests/ keep getting included in the fpm package
        # despite being excluded here. this is in contrast to python files in packages/
        # the pip wheel correctly excludes both
        build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'deb', '-s',
            'python', '--verbose', '--no-auto-depends',
            '--python-scripts-executable', '/usr/bin/env python3',
            '--python-bin', 'python3',
            '--python-package-name-prefix', 'python3',
            '--depends=python3-pkg-resources,python3-serial,python3-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0',
            '..',
        ), cwd='dist')
        wash()
        remove(SETUP_CFG)

    setup_options['cmdclass'] = dict(
        bdist_rpm=new_command(bdist_rpm),
        bdist_deb=new_command(bdist_deb),
        **COMMANDS
    )

    # run the setuptools setup()
    setup(script_args=['bdist_rpm'], **setup_options)
    setup(script_args=['bdist_deb'], **setup_options)
