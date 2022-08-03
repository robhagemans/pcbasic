"""
PC-BASIC make.common
Python, Windows, MacOS and Linux packaging utilities

(c) 2015--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""


import sys
import os
import shutil
import glob
import json
import datetime
from subprocess import check_output, CalledProcessError
from contextlib import contextmanager

from PIL import Image

from pcbasic import NAME, VERSION, AUTHOR, COPYRIGHT
from pcbasic.data import ICON
from docs import make_htmldoc, make_usage, make_man


# paths

# root location
HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

BUILD_PATH = os.path.join(HERE, 'build')
RESOURCE_PATH = os.path.join(BUILD_PATH, 'resources')
DOC_PATH = os.path.join(BUILD_PATH, 'doc')
USAGE_PATH = os.path.join(HERE, 'pcbasic', 'data')

ICON_PATTERN = os.path.join(RESOURCE_PATH, 'pcbasic.{format}')

STAMP_FILE = os.path.join(HERE, 'pcbasic', 'basic', 'data', 'release.json')

USAGE_NAME = 'USAGE.txt'
MAN_NAME = 'pcbasic.1.gz'
HTMLDOC_NAME = 'PC-BASIC_documentation.html'


###############################################################################
# make targets and components

def make_clean():
    """clean the workspace of build files; leave in-place compiled files"""
    # remove traces of egg
    for path in glob.glob(os.path.join(HERE, '*.egg-info')):
        prune(path)
    # remove intermediate builds
    prune(BUILD_PATH)
    # remove bytecode files
    for root, dirs, files in os.walk(HERE):
        for name in dirs:
            if name == '__pycache__':
                prune(os.path.join(root, name))
        for name in files:
            if (name.endswith('.pyc') or name.endswith('.pyo')) and 'test' not in root:
                remove(os.path.join(root, name))
    # remove release stamp
    remove(STAMP_FILE)

def prepare():
    """Prepare for sdist and wheel builds."""
    make_clean()
    stamp_release()
    make_docs()

def make_docs():
    """Build manfile, usage, html and pdf documentation."""
    mkdir(DOC_PATH)
    make_man(DOC_PATH, MAN_NAME)
    make_htmldoc(DOC_PATH, HTMLDOC_NAME)
    make_usage(USAGE_PATH, USAGE_NAME)

def make_local():
    """Build manfile, usage, html and pdf documentation."""
    make_usage(USAGE_PATH, USAGE_NAME)


###############################################################################
# release stamp

# git commit hash
try:
    TAG = check_output(['git', 'describe', '--tags'], cwd=HERE).strip().decode('ascii', 'ignore')
    COMMIT = check_output(
        ['git', 'describe', '--always'], cwd=HERE
    ).strip().decode('ascii', 'ignore')
except (EnvironmentError, CalledProcessError):
    TAG = u''
    COMMIT = u''

# release info
RELEASE_ID = {
    u'version': VERSION,
    u'tag': TAG,
    u'commit': COMMIT,
    u'timestamp': str(datetime.datetime.now())
}

def stamp_release():
    """Place the relase ID file."""
    json_str = json.dumps(RELEASE_ID)
    with open(STAMP_FILE, 'w') as release_json:
        release_json.write(json_str)


###############################################################################
# icon

def build_icon():
    """Create an icon file for the present platform."""
    flat = (_b for _row in ICON for _b in _row)
    rgb = ((_b*255,)*3 for _b in flat)
    rgbflat = (_b for _tuple in rgb for _b in _tuple)
    imgstr = bytes(rgbflat)
    width, height = len(ICON[0]), len(ICON)
    img = Image.frombytes('RGB', (width, height), imgstr)
    format = {'win32': 'ico', 'darwin': 'icns'}.get(sys.platform, 'png')
    icon_file = ICON_PATTERN.format(format=format)
    with os_safe('building icon file', icon_file):
        img.resize((width*2, height*2)).save(icon_file)


###############################################################################
# shell utilities

@contextmanager
def os_safe(message, name):
    """Catch and report environment errors."""
    print('... {} {} ... '.format(message, name), end='')
    try:
        yield
    except EnvironmentError as err:
        print(err)
    else:
        print('ok')


def prune(path):
    """Recursively remove a directory."""
    with os_safe('pruning', path):
        shutil.rmtree(path)

def remove(path):
    """Remove a file."""
    with os_safe('removing', path):
        os.remove(path)

def mkdir(name):
    """Create a directory and all parents needed (mkdir -p)."""
    with os_safe('creating', name):
        os.makedirs(name)
