from .makeusage import makeusage
from .makeman import makeman
from .makedoc import makedoc

def build_docs():
    makeusage()
    makeman()
    makedoc()
