"""
PC-BASIC - plat.py
Platform identification

(c) 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

# get basepath (__file__ is undefined in pyinstaller packages)
import sys
import os
if hasattr(sys, 'frozen'):
    # we're a package, get the directory of the packaged executable
    _basepath = os.path.dirname(sys.executable)
else:
    # get the directory of this file
    _basepath = os.path.dirname(os.path.realpath(__file__))
if type(_basepath) == bytes:
    # __file__ is a bytes object, not unicode
    _basepath = _basepath.decode(sys.getfilesystemencoding())

# directories
encoding_dir = os.path.join(_basepath, u'codepage')
font_dir = os.path.join(_basepath, u'font')
info_dir = os.path.join(_basepath, u'data')



# create temporary directory
import tempfile
temp_dir = tempfile.mkdtemp(prefix=u'pcbasic-')

# PC-BASIC version
try:
    with open(os.path.join(info_dir, u'version.txt')) as f:
        version = f.read().rstrip()
except EnvironmentError:
    version = ''
