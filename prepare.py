#!/usr/bin/env python2
import sys
import os
cwd = os.getcwd()
os.chdir('docsrc')
sys.path.insert(0, os.getcwd())
from makeusage import makeusage
from makeman import makeman
from makedoc import makedoc
makeusage()
makeman()
makedoc()
os.chdir(cwd)
