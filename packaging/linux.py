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


from .common import wash, new_command, _build_icon, _build_manifest, _stamp_release, _mkdir, _remove
from .common import HERE, COMMANDS, INCLUDE_FILES, EXCLUDE_FILES, PLATFORM_TAG


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

    SETUP_CFG = os.path.join(HERE, 'setup.cfg')

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
        # prepare a setup.cfg in the root
        # so that desktop files get picked up by setup.py install and hence by fpm
        with open(SETUP_CFG, 'w') as setup_cfg:
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
        _remove(SETUP_CFG)

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
        _remove(SETUP_CFG)

    SETUP_OPTIONS['cmdclass'] = dict(
        bdist_rpm=new_command(bdist_rpm),
        bdist_deb=new_command(bdist_deb),
        **COMMANDS
    )

    # run the setuptools setup()
    setup(script_args=['bdist_rpm'], **SETUP_OPTIONS)
    setup(script_args=['bdist_deb'], **SETUP_OPTIONS)
