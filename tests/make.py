#!/usr/bin/env python3
""" PC-BASIC test creation

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TESTNAME = sys.argv[1]

if TESTNAME.endswith('/'):
    TESTNAME = TESTNAME[:-1]

# e.g. basic/gwbasic/TestName
try:
    DIR, TESTNAME = os.path.split(TESTNAME)
    _, PRESET = os.path.split(DIR)
except ValueError:
    PRESET = 'gwbasic'

PATH = os.path.join(HERE, 'basic', PRESET)
TEMPLATE = os.path.join(HERE, '_templates', PRESET)

if not os.path.isdir(TEMPLATE):
    sys.exit('Test template {} not found.'.format(TEMPLATE))

if not os.path.isdir(PATH):
    os.mkdir(PATH)

shutil.copytree(TEMPLATE, os.path.join(PATH, TESTNAME))
