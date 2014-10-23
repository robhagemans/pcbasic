#
# PC-BASIC 3.23  - plat.py
#
# Platform identification
# 
# (c) 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#

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
info_dir = os.path.join(basepath, 'info')

# default filenames
config_name = 'PCBASIC.INI'
state_name = 'PCBASIC.SAV'

# OS-specific stdin/stdout selection
# no stdin/stdout access allowed on packaged apps
if system in ('OSX', 'Windows'):
    stdin_is_tty, stdout_is_tty = True, True
    stdin, stdout = None, None
else:
    # Unix, Linux including Android
    try:
        stdin_is_tty = sys.stdin.isatty()
        stdout_is_tty = sys.stdout.isatty()
    except AttributeError:
        stdin_is_tty, stdout_is_tty = True, True
        stdin, stdout = None, None
    stdin, stdout = sys.stdin, sys.stdout

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

