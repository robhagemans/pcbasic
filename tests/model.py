#!/usr/bin/env python3
""" PC-BASIC model creation

(c) 2020--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import sys
import os
import shutil
import json
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

GW_OPTIONS = sys.argv[2:]

with open(os.path.join(HERE, '_settings', 'settings.json')) as settings:
    SETTINGS = json.load(settings)[PRESET]

PATH = os.path.join(HERE, 'basic', PRESET, TESTNAME)
MODEL = os.path.join(PATH, 'model')
BAS = 'TEST.BAS'

if not os.path.isdir(PATH):
    sys.exit('Test {} not found.'.format(TEMPLATE))

shutil.rmtree(MODEL, ignore_errors=True)
shutil.copytree(
    PATH, MODEL,
    ignore=lambda _path, _names: list(set(['output', 'model']) & set(_names))
)
CALL = [
    'dosbox',
    '-conf', '{}'.format(os.path.join('_settings', SETTINGS['conf'])),
    '-c', 'MOUNT C {}'.format(MODEL),
    '-c', 'MOUNT E {}'.format(SETTINGS['dir']),
    '-c', 'C:',
    '-c', 'E:\\{} {} {}'.format(SETTINGS['exe'], BAS, ' '.join(GW_OPTIONS)),
    '-c', 'EXIT'
]
print('calling:', ' '.join(CALL))
subprocess.call(CALL, cwd=HERE)

for name in os.listdir(PATH):
    if name == 'model':
        continue
    delpath = os.path.join(MODEL, name)
    print('removing: {}'.format(delpath))
    if os.path.isdir(name):
        shutil.rmtree(delpath)
    else:
        os.remove(delpath)
