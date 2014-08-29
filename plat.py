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
        system = 'Unix'

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
