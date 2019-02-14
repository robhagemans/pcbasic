"""
PC-BASIC - packaging.linux
Linux packaging

(c) 2015--2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import shutil
import subprocess
from subprocess import check_output, CalledProcessError
from io import open

from setuptools import setup


from .common import wash, new_command, _build_icon, _build_manifest, _stamp_release, _mkdir, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG


def package(SETUP_OPTIONS, NAME, AUTHOR, VERSION, SHORT_VERSION, COPYRIGHT):


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
        _mkdir('resources')
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
        _mkdir('dist/')
        if os.path.exists('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,)):
            os.unlink('dist/python-pcbasic-%s-1.noarch.rpm' % (VERSION,))
        _stamp_release()
        _gather_resources()
        _build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'rpm', '-s', 'python', '--no-auto-depends',
            '--depends=pyserial,SDL2,SDL2_gfx',
            '..'
        ), cwd='dist')
        wash()

    def bdist_deb():
        """create .deb package (requires fpm)"""
        wash()
        _mkdir('dist/')
        if os.path.exists('dist/python-pcbasic_%s_all.deb' % (VERSION,)):
            os.unlink('dist/python-pcbasic_%s_all.deb' % (VERSION,))
        _stamp_release()
        _gather_resources()
        _build_manifest(INCLUDE_FILES, EXCLUDE_FILES)
        subprocess.call((
            'fpm', '-t', 'deb', '-s', 'python', '--no-auto-depends',
            '--depends=python-serial,python-parallel,libsdl2-2.0-0,libsdl2-gfx-1.0-0',
            '..'
        ), cwd='dist')
        wash()

    SETUP_OPTIONS['cmdclass'] = dict(
        bdist_rpm=new_command(bdist_rpm),
        bdist_deb=new_command(bdist_deb),
        **COMMANDS
    )


    # run the setuptools setup()
    setup(script_args=['bdist_rpm'], **SETUP_OPTIONS)
    setup(script_args=['bdist_deb'], **SETUP_OPTIONS)
