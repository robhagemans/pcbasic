#
# PC-BASIC 3.23 - android-logging.py
#
# Workaround for mssing logging module in PyGame subset for Android
# 
# (c) 2013, 2014 Rob Hagemans 
#
# This file is released under the GNU GPL version 3. 
# please see text file COPYING for licence terms.
#


try:
    import logging
except ImportError:
    import sys

    class Logger:
        def basicConfig(self, *dummy, **kwdummy):
            pass

        def info(self, s):
            sys.stderr.write('INFO: ' + s + '\n')

        def debug(self, s):
            sys.stderr.write('DEBUG: ' + s + '\n')

        def warning(self, s):
            sys.stderr.write('WARNING: ' + s + '\n')

        def critical(self, s):
            sys.stderr.write('CRITICAL: ' + s + '\n')

    logging = Logger()
    
