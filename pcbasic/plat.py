"""
PC-BASIC - plat.py
Platform identification

(c) 2014, 2015 Rob Hagemans
This file is released under the GNU GPL version 3.
"""

import platform
if platform.system() == 'Windows':
    system = b'Windows'
elif platform.system() == 'Linux':
    system = b'Linux'
elif platform.system() == 'Darwin':
    system = b'OSX'
else:
    # Everything else. Assume it's a Unix.
    system = b'Unknown_OS'


# preferred locale
import locale
# this is necessary for curses and *maybe* for clipboard handling
# there's only one locale setting so best to do it all upfront here
# NOTE that this affects str.upper() etc.
locale.setlocale(locale.LC_ALL, '')
# this platform's preferred encoding
preferred_encoding = locale.getpreferredencoding()

# get basepath (__file__ is undefined in pyinstaller packages)
import sys

import os
if hasattr(sys, 'frozen'):
    # we're a package, get the directory of the packaged executable
    basepath = os.path.dirname(sys.executable)
else:
    # get the directory of this file
    basepath = os.path.dirname(os.path.realpath(__file__))
if type(basepath) == bytes:
    basepath = basepath.decode(preferred_encoding)

# directories
encoding_dir = os.path.join(basepath, u'codepage')
font_dir = os.path.join(basepath, u'font')
info_dir = os.path.join(basepath, u'data')
system_config_dir = info_dir
# user home
home_dir = os.path.expanduser(u'~')

# user configuration and state directories
if system == b'Windows':
    user_config_dir = os.path.join(os.getenv(u'APPDATA'), u'pcbasic')
    state_path = user_config_dir
elif system == b'OSX':
    user_config_dir = os.path.join(home_dir, u'Library/Application Support/pcbasic')
    state_path = user_config_dir
elif system == b'Android':
    user_config_dir = info_dir
    state_path = info_dir
else:
    xdg_data_home = os.environ.get(u'XDG_DATA_HOME') or os.path.join(home_dir, u'.local', u'share')
    xdg_config_home = os.environ.get(u'XDG_CONFIG_HOME') or os.path.join(home_dir, u'.config')
    user_config_dir = os.path.join(xdg_config_home, u'pcbasic')
    state_path = os.path.join(xdg_data_home, u'pcbasic')
if not os.path.exists(state_path):
    os.makedirs(state_path)


# OS-specific stdin/stdout selection
# no stdin/stdout access allowed on packaged apps in OSX
if system == b'OSX':
    stdin_is_tty, stdout_is_tty = True, True
    has_stdin, has_stdout = False, False
elif system == b'Windows':
    stdin_is_tty, stdout_is_tty = True, True
    has_stdin, has_stdout = True, True
else:
    # Unix, Linux including Android
    try:
        stdin_is_tty = sys.stdin.isatty()
        stdout_is_tty = sys.stdout.isatty()
        has_stdin, has_stdout = True, True
    except AttributeError:
        stdin_is_tty, stdout_is_tty = True, True
        has_stdin, has_stdout = False, False

if system == b'Android':
    # always use the same location on Android
    # to ensure we can delete at start
    # since we can't control exits
    temp_dir = os.path.join(basepath, u'temp')
else:
    # create temporary directory
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix=u'pcbasic-')

# PC-BASIC version
try:
    with open(os.path.join(info_dir, u'version.txt')) as f:
        version = f.read().rstrip()
except EnvironmentError:
    version = ''
