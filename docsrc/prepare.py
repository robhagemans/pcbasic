#!/usr/bin/env python2

from makeusage import makeusage
from makeman import makeman
from makedoc import makedoc

def build_docs():
    makeusage()
    makeman()
    makedoc()

if __name__ == '__main__':
    build_docs()
