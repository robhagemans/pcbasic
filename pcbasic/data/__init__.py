"""
PC-BASIC - data package
Fonts, codepages and BASIC resources

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkg_resources


CODEPAGE_DIR = u'codepages'
PROGRAM_DIR = u'programs'
FONT_DIR = u'fonts'

CODEPAGES = [name.split(u'.', 1)[0] for name in pkg_resources.resource_listdir(__name__, CODEPAGE_DIR) if name.lower().endswith(u'.ucp')]
PROGRAMS = (name for name in pkg_resources.resource_listdir(__name__, PROGRAM_DIR) if name.lower().endswith(u'.bas'))
FONTS = [name.split(u'_', 1)[0] for name in pkg_resources.resource_listdir(__name__, FONT_DIR) if name.lower().endswith(u'.hex')]


###############################################################################
# exceptions

class ResourceFailed(Exception):
    """Failed to load resource"""

    def __init__(self, spec=u'resource', name=u''):
        self._message = u'Failed to load {0} {1}'.format(spec, name)

    def __str__(self):
        return self._message


###############################################################################
# font files

def get_data(name):
    """Wrapper for resource_string."""
    try:
        # this should return None if not available, I thought, but it doesn't
        return pkg_resources.resource_string(__name__, name)
    except EnvironmentError:
        return None

def read_font_files(families, height):
    """Retrieve contents of font files."""
    return [
        get_data(u'%s/%s_%02d.hex' % (FONT_DIR, name, height))
        for name in families]


###############################################################################
# codepage files

def read_codepage_file(codepage_name):
    """Retrieve contents of codepage file."""
    resource = get_data('%s/%s.ucp' % (CODEPAGE_DIR, codepage_name))
    if resource is None:
        raise ResourceFailed(u'codepage', codepage_name)
    return resource

###############################################################################
# program files

def read_program_file(name):
    """Read a bundled BASIC program file."""
    program = ('%s/%s' % (PROGRAM_DIR, name))
    if program is None:
        raise ResourceFailed(u'bundled program', name)
    return program
