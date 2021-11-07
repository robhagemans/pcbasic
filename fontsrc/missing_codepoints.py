#!/usr/bin/env python3
# tabulate codepoints needed

import os
import sys

CODEPAGE_DIR = '../pcbasic/data/codepages/'
filename = sys.argv[1]

codepoints_needed = set()
for ucp_name in os.listdir(CODEPAGE_DIR):
    with open(CODEPAGE_DIR + ucp_name) as ucp:
        for line in ucp:
            if not line or line.startswith('#'):
                continue
            _, cps = line.split(':')
            ustr = ''.join(chr(int(codepoint.strip(), 16)) for codepoint in cps.split(','))
            codepoints_needed.add(ustr)


#
# scan a .hex file for missing codepoints

codepoints_found = set()
with open(filename) as source:
    for line in sorted(source):
        if line.startswith('#'):
            continue
        if not line.strip():
            continue
        cps, _ = line.split(':')
        ustr = ''.join(chr(int(codepoint.strip(), 16)) for codepoint in cps.split(','))
        codepoints_found.add(ustr)

missing = codepoints_needed - codepoints_found

def _print_end(start, last_missing):
    if last_missing is not None:
        if last_missing != start:
            print(f'--{last_missing:04x}')
        else:
            print()

start = None
last_missing = None
for ustr in sorted(missing):
    if len(ustr) > 1:
        _print_end(start, last_missing)
        print(','.join(f'{ord(_c):04x}' for _c in ustr))
        last_missing = None
        start = None
    else:
        codepoint = ord(ustr)
        if last_missing is None or codepoint - last_missing > 1:
            _print_end(start, last_missing)
            print(f'{codepoint:04x}', end='')
            start = codepoint
        last_missing = codepoint
_print_end(start, last_missing)
