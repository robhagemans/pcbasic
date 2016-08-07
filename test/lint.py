#!/usr/bin/env python2
from pylint import epylint
import os
import sys


def lint_files(path, filenames, exclude=[]):
    for namext in filenames:
        name, ext = os.path.splitext(namext)
        if ext != '.py':
            continue
        if name in exclude:
            continue
        fullname = os.path.join(path, namext)
        print fullname
        epylint.lint(fullname, ['--ignored-modules=pygame,numpy,pygame.mixer', '--ignored-classes=Serial,pygame.Surface', '--errors-only'])


basedir = os.path.join('..', 'pcbasic')

args = sys.argv[1:]
if not args or args == ['--all']:
    exclude = ['example', 'video_pygame']

    for path, _, filenames in os.walk(basedir):
        lint_files(path, filenames, exclude)
        epylint.lint(os.path.join(basedir, 'interface', 'video_pygame.py'),
            ['--ignored-modules=pygame,numpy,pygame.mixer', '--ignored-classes=Serial,pygame.Surface', '--errors-only', '--disable=too-many-function-args,unexpected-keyword-arg'])

else:
    lint_files(basedir, args)
