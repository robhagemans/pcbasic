"""
PC-BASIC - GW-BASIC/BASICA/Cartridge BASIC compatible interpreter

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

__version__ = b'16.12.0rc0'
__copyright__ = b'(C) Copyright 2013--2018 Rob Hagemans.'


GREETING = (
    'KEY ON:PRINT "PC-BASIC {version}":PRINT "{copyright}":'
    'PRINT USING "##### Bytes free"; FRE(0)'.format(
        version=__version__, copyright=__copyright__))
