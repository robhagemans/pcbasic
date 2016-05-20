#!/usr/bin/env python2
from pylint import epylint
import os

exclude = ['example', 'video_pygame']

for path, _, filenames in os.walk(os.path.join('..', 'pcbasic')):
    for namext in filenames:
        name, ext = os.path.splitext(namext)
        if ext != '.py':
            continue
        if name in exclude:
            continue
        fullname = os.path.join(path, namext)
        print fullname
        epylint.lint(fullname, ['--ignored-modules=pygame,numpy,pygame.mixer', '--ignored-classes=Serial,pygame.Surface', '--errors-only'])

epylint.lint(os.path.join('..','pcbasic','interface','video_pygame.py'),
        ['--ignored-modules=pygame,numpy,pygame.mixer', '--ignored-classes=Serial,pygame.Surface', '--errors-only', '--disable=too-many-function-args,unexpected-keyword-arg'])
