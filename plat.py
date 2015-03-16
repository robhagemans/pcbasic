"""
PC-BASIC 3.23  - plat.py
Platform identification

(c) 2014 Rob Hagemans 
This file is released under the GNU GPL version 3. 
"""

try:
    import android
    system = 'Android'
except ImportError:
    import platform
    if platform.system() == 'Windows':
        system = 'Windows'
    elif platform.system() == 'Linux':
        system = 'Linux'
    elif platform.system() == 'Darwin':
        system = 'OSX'
    else:
        # Everything else. Assume it's a Unix.            
        system = 'Unknown_OS'

# get basepath (__file__ is undefined in pyinstaller packages)
import sys
import os
if hasattr(sys, "frozen"):
    # we're a package, get the directory of the packaged executable 
    basepath = os.path.dirname(sys.executable)
else:
    # get the directory of this file
    basepath = os.path.dirname(os.path.realpath(__file__))

# directories
encoding_dir = os.path.join(basepath, 'encoding')
font_dir = os.path.join(basepath, 'font')
info_dir = os.path.join(basepath, 'data')
# use home
home_dir = os.path.expanduser('~')

# configuration and state
config_name = 'PCBASIC.INI'
state_name = 'PCBASIC.SAV'
system_config_dir = os.path.join(basepath, 'config')
if system == 'Windows':
    user_config_dir = os.path.join(os.getenv('APPDATA'), 'pcbasic')
    state_path = user_config_dir
elif system == 'OSX':
    user_config_dir = os.path.join(home_dir, 'Library/Application Support/pcbasic')
    state_path = user_config_dir
elif system == 'Android':
    user_config_dir = info_dir
    state_path = info_dir
else:
    import xdg.BaseDirectory
    user_config_dir = os.path.join(xdg.BaseDirectory.xdg_config_home, 'pcbasic')
    state_path = os.path.join(xdg.BaseDirectory.xdg_data_home, 'pcbasic')
if not os.path.exists(state_path):
    os.makedirs(state_path)


# OS-specific stdin/stdout selection
# no stdin/stdout access allowed on packaged apps in OSX
if system == 'OSX':
    stdin_is_tty, stdout_is_tty = True, True
    has_stdin, has_stdout = False, False
elif system == 'Windows':
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

if system == 'Android':
    # always use the same location on Android
    # to ensure we can delete at start
    # since we can't control exits
    temp_dir = os.path.join(basepath, 'temp')
else:
    # create temporary directory
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix='pcbasic-')    
    
# PC_BASIC version
try:
    version = open(os.path.join(info_dir, 'VERSION')).read().rstrip()
except (IOError, OSError):
    version = ''

