#!/usr/bin/env python2

from docsrc.makeusage import makeusage
from docsrc.makeman import makeman
from docsrc.makedoc import makedoc

def build_docs():
    makeusage()
    makeman()
    makedoc()

if __name__ == '__main__':
    build_docs()
