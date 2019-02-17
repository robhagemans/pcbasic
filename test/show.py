#!/usr/bin/env python
""" PC-BASIC test diagnostics

(c) 2019 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import os
import sys
import subprocess

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

PATH = os.path.join(HERE, 'basic', PRESET, TESTNAME)
MODEL = os.path.join(PATH, 'model')
OUTPUT = os.path.join(PATH, 'output')

for name in os.listdir(MODEL):
    print()
    print(name, '-'*80)
    subprocess.call(['colordiff', os.path.join(OUTPUT, name), os.path.join(MODEL, name)])
