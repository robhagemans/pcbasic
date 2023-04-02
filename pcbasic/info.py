"""
PC-BASIC - info
platform information

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import platform
import importlib

from .compat import which
from .basic import NAME, VERSION, LONG_VERSION, COPYRIGHT


def get_version_info():
    """Retrieve long version info."""
    return u'%s %s\n%s\n' % (NAME, LONG_VERSION, COPYRIGHT)

def get_platform_info():
    """Retrieve information about operating system and installed modules."""
    info = []
    info.append(u'\nPLATFORM')
    info.append(u'os: %s' % platform.platform())
    frozen = getattr(sys, 'frozen', '') or ''
    info.append(
        u'python: %s %s %s' % (
        sys.version.replace('\n', ''), ' '.join(platform.architecture()), frozen))
    info.append(u'\nMODULES')
    modules = ('pyaudio', 'serial', 'parallel')
    for module in modules:
        try:
            m = importlib.import_module(module)
        except Exception:
            info.append(u'%s: --' % module)
        else:
            for version_attr in ('__version__', 'version', 'VERSION'):
                try:
                    name = module.split('.')[-1]
                    version = getattr(m, version_attr)
                    if isinstance(version, bytes):
                        version = version.decode('ascii', 'ignore')
                    info.append(u'%s: %s' % (name, version))
                    break
                except AttributeError:
                    pass
            else:
                info.append(u'%s: available' % module)
    info.append(u'\nLIBRARIES')
    try:
        from .interface import video_sdl2
        video_sdl2._import_sdl2()

        info.append(u'sdl2: %s' % (video_sdl2.sdl2.sdl2_lib.libfile,))
        if video_sdl2:
            info.append(u'sdl2_gfx: %s' % (video_sdl2.sdl2.gfx_lib.libfile, ))
        else:
            info.append(u'sdl2_gfx: --')
    except ImportError as e:
        raise
        info.append(u'sdl2: --')
        sdl2 = None
    info.append(u'\nEXTERNAL TOOLS')
    tools = (u'notepad', u'lpr', u'paps', u'beep', u'pbcopy', u'pbpaste')
    for tool in tools:
        location = which(tool) or u'--'
        info.append(u'%s: %s' % (tool, location))
    info.append(u'')
    return u'\n'.join(info)
