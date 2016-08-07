#!/usr/bin/env python2

""" PC-BASIC test script

(c) 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import subprocess
import shutil
import filecmp

def is_same(file1, file2):
    try:
        return filecmp.cmp(file1, file2, shallow=False)
    except EnvironmentError:
        return False

args = sys.argv[1:]

if not args or args == ['--all']:
    args = [f for f in sorted(os.listdir('.')) if os.path.isdir(f)]

numtests = 0
failed = []
knowfailed = []

for name in args:
    print 'Running test %s .. ' % name,
    if not os.path.isdir(name):
        print 'no such test.'
        continue
    output_dir = os.path.join(name, 'output')
    model_dir = os.path.join(name, 'model')
    known_dir = os.path.join(name, 'known')
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)
    for filename in os.listdir(name):
        if os.path.isfile(os.path.join(name, filename)):
            shutil.copy(os.path.join(name, filename), os.path.join(output_dir, filename))
    top = os.getcwd()
    os.chdir(output_dir)
    sys.stdout.flush()
    subprocess.Popen(['python', os.path.join('..','..','..','pcbasic.py'), '--interface=none'],
            stdin=sys.stdin, stdout=open(os.devnull, 'w'), stderr=open(os.devnull, 'w')).wait()
    os.chdir(top)
    passed = True
    known = True
    failfiles = []
    for filename in os.listdir(model_dir):
        if not is_same(os.path.join(output_dir, filename), os.path.join(model_dir, filename)):
            failfiles.append(filename)
            known = os.path.isdir(known_dir) and is_same(os.path.join(output_dir, filename), os.path.join(known_dir, filename))
            passed = False
    for filename in os.listdir(output_dir):
        if not os.path.isfile(os.path.join(output_dir, filename)):
            failfiles.append(filename)
            passed = False
            known = False
    if not passed:
        if not known:
            print 'FAILED: difference in %s.' % ' '.join(failfiles)
            failed.append(name)
        else:
            print 'known failure: difference in %s.' % ' '.join(failfiles)
            knowfailed.append(name)
    else:
        print 'passed.'
        shutil.rmtree(output_dir)
    numtests += 1

print
print 'Ran %d tests:' % numtests
if failed:
    print '    %d new failures: %s' % (len(failed), ' '.join(failed))
if knowfailed:
    print '    %d known failures: %s' % (len(knowfailed), ' '.join(knowfailed))
numpass = numtests - len(failed) - len(knowfailed)
if numpass:
    print '    %d passes' % numpass
