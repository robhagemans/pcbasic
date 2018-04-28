#!/usr/bin/env python2
from pylint import epylint
import os
import sys

CONFIG = [
    '--ignored-modules=pygame,numpy,pygame.mixer,msvcrt',
    '--ignored-classes=Serial,pygame.Surface,Namespace',
    '--errors-only',
]

def lint_files(path, filenames, exclude=[]):
    for namext in filenames:
        name, ext = os.path.splitext(namext)
        if ext != '.py':
            continue
        if name in exclude:
            continue
        fullname = os.path.join(path, namext)
        print fullname
        epylint.lint(fullname, CONFIG)


basedir = os.path.join('..', 'pcbasic')

args = sys.argv[1:]
if not args or args == ['--all']:
    for path, _, filenames in os.walk(basedir):
        lint_files(path, filenames)
else:
    lint_files(basedir, args)
