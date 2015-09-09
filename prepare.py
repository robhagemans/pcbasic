#!/usr/bin/env python2
import os
cwd = os.getcwd()
os.chdir('docsrc')
from docsrc.makeusage import makeusage
from docsrc.makeman import makeman
from docsrc.makedoc import makedoc
makeusage()
makeman()
makedoc()
os.chdir(cwd)
