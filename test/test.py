#!/usr/bin/env python2

""" PC-BASIC test script

(c) 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import sys
import os
import shutil
import filecmp
import contextlib
import traceback
import time

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

import pcbasic

def is_same(file1, file2):
    try:
        return filecmp.cmp(file1, file2, shallow=False)
    except EnvironmentError:
        return False

def count_diff(file1, file2):
    lines1 = open(file1).readlines()
    lines2 = open(file2).readlines()
    n = len(lines1)
    count = 0
    for one, two in zip(lines1, lines2):
        if one != two:
            count += 1
    return n, count

@contextlib.contextmanager
def suppress_stdio(do_suppress):
    if not do_suppress:
        yield
    else:
        sys.stderr, err = open(os.devnull, 'w'), sys.stderr
        sys.stdout, out = open(os.devnull, 'w'), sys.stdout
        yield
        sys.stderr = err
        sys.stdout = out



args = sys.argv[1:]

do_suppress = '--loud' not in args

try:
    args.remove('--loud')
except ValueError:
    pass

if not args or '--all' in args:
    args = [f for f in sorted(os.listdir('.'))
            if os.path.isdir(f) and os.path.isdir(os.path.join(f, 'model'))]


numtests = 0
failed = []
knowfailed = []

start_time = time.time()
start_clock = time.clock()

for name in args:
    print '\033[00;37mRunning test \033[01m%s \033[00;37m.. ' % name,
    if not os.path.isdir(name):
        print '\033[01;31mno such test.\033[00;37m'
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
    # -----------------------------------------------------------
    # suppress output and logging and call PC-BASIC
    with suppress_stdio(do_suppress):
        crash = None
        try:
            pcbasic.run('--interface=none', '--debug')
        except Exception as e:
            crash = e
            traceback.print_tb(sys.exc_info()[2])
    # -----------------------------------------------------------
    os.chdir(top)
    passed = True
    known = True
    failfiles = []
    for path, dirs, files in os.walk(model_dir):
        for f in files:
            filename = os.path.join(path[len(model_dir)+1:], f)
            if not is_same(os.path.join(output_dir, filename), os.path.join(model_dir, filename)):
                failfiles.append(filename)
                known = os.path.isdir(known_dir) and is_same(os.path.join(output_dir, filename), os.path.join(known_dir, filename))
                passed = False
    for path, dirs, files in os.walk(output_dir):
        for f in files:
            filename = os.path.join(path[len(output_dir)+1:], f)
            if not os.path.isfile(os.path.join(output_dir, filename)):
                failfiles.append(filename)
                passed = False
                known = False
    if crash or not passed:
        if crash:
            print '\033[01;31mEXCEPTION.\033[00;37m'
            print '    %s' % repr(e)
            failed.append(name)
        elif not known:
            print '\033[01;31mfailed.\033[00;37m'
            for failname in failfiles:
                try:
                    n, count = count_diff(os.path.join(output_dir, failname), os.path.join(model_dir, failname))
                    pct = 100.*count/float(n) if n != 0 else 0
                    print '    %s: %d lines, %d differences (%3.2f %%)' % (failname, n, count, pct)
                except EnvironmentError as e:
                    print '    %s: %s' % (failname, e)
            failed.append(name)
        else:
            print '\033[00;36mknown failure.\033[00;37m'
            for failname in failfiles:
                try:
                    n, count = count_diff(os.path.join(output_dir, failname), os.path.join(model_dir, failname))
                    pct = 100.*count/float(n) if n != 0 else 0
                    print '    %s: %d lines, %d differences (%3.2f %%)' % (failname, n, count, pct)
                except EnvironmentError as e:
                    print '    %s: %s' % (failname, e)
            knowfailed.append(name)
    else:
        print '\033[00;32mpassed.\033[00;37m'
        shutil.rmtree(output_dir)
    numtests += 1

print
print '\033[00mRan %d tests in %.2fs (wall) %.2fs (cpu):' % (numtests, time.time() - start_time, time.clock() - start_clock)
if failed:
    print '    %d new failures: \033[01;31m%s\033[00m' % (len(failed), ' '.join(failed))
if knowfailed:
    print '    %d known failures: \033[00;36m%s\033[00m' % (len(knowfailed), ' '.join(knowfailed))
numpass = numtests - len(failed) - len(knowfailed)
if numpass:
    print '    %d passes' % numpass
