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
    elif plaform.system() == 'Darwin':
        system = 'OSX'
    else:
        # Everything else. Assume it's a Unix.            
        system = 'Unix'

