#!/usr/bin/env python3
""" PC-BASIC test diagnostics

(c) 2020--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from __future__ import print_function

import os
import sys
import subprocess
import difflib
from io import open

try:
    from colorama import init
    init()
except ImportError:
    # only needed on Windows
    # without it we still work but look a bit garbled
    pass


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
ACCEPTED = os.path.join(PATH, 'accepted')
KNOWN = os.path.join(PATH, 'known')
OUTPUT = os.path.join(PATH, 'output')


def count_diff(lines1, lines2):
    n = len(lines1)
    count = 0
    for one, two in zip(lines1, lines2):
        if one != two:
            count += 1
    return n, count

def print_diffline(line):
    if line.startswith(u'+'):
        print('\033[0;32m', end='')
    elif line.startswith(u'-'):
        print('\033[0;31m', end='')
    elif not line.startswith(u'@'):
        print('\033[0;36m', end='')
    if not line.startswith(u'@') and not line.startswith(u'+++') and not line.startswith(u'---'):
        line = line.encode('unicode_escape', errors='replace').decode('latin-1', errors='replace')
    else:
        line = line.strip()
    print(line, end='')
    print('\033[0m')

if not os.path.isdir(OUTPUT):
    print('no differences')

for name in os.listdir(MODEL):
    try:
        with open(os.path.join(OUTPUT, name), 'rb') as output:
            outlines = output.readlines()
    except EnvironmentError:
        print(name, 'vs. model: file missing')
        continue
    with open(os.path.join(MODEL, name), 'rb') as model:
        modlines = model.readlines()

    try:
        n, count = count_diff(outlines, modlines)
        pct = 100.*count/float(n) if n != 0 else 0
        print('%s vs. model: %d lines, %d differences (%3.2f %%)' % (name, n, count, pct))
    except EnvironmentError as e:
        print('%s vs. model: %s' % (name, e))

    print('-'*80)

    try:
        with open(os.path.join(ACCEPTED, name), 'rb') as accepted:
            acclines = accepted.readlines()
    except EnvironmentError:
        acclines = []
    outlines = [_line.decode('latin-1') for _line in outlines]
    modlines = [_line.decode('latin-1') for _line in modlines]
    acclines = [_line.decode('latin-1') for _line in acclines]
    for line in difflib.unified_diff(outlines, modlines, 'output', 'model', n=10):
        print_diffline(line)
    print()
    if acclines:
        print(name, 'vs. accepted')
        print('-'*80)
        for line in difflib.unified_diff(outlines, acclines, 'output', 'accepted', n=10):
            print_diffline(line)
        print()

for name in os.listdir(OUTPUT):
    if (
            not os.path.exists(os.path.join(MODEL, name))
            and not os.path.exists(os.path.join(PATH, name))
        ):
        print(name, 'vs. model: surplus file')
