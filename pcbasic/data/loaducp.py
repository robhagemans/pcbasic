"""
PC-BASIC - data package
UCP codepage loader

(c) 2013--2018 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkg_resources
import logging

from .resources import get_data

CODEPAGE_DIR = u'codepages'
CODEPAGE_PATTERN = u'{path}/{name}.ucp'
CODEPAGES = [name.split(u'.', 1)[0] for name in pkg_resources.resource_listdir(__name__, CODEPAGE_DIR) if name.lower().endswith(u'.ucp')]


def read_codepage(codepage_name):
    """Read a codepage file and convert to codepage dict."""
    codepage = {}
    for line in get_data(CODEPAGE_PATTERN, path=CODEPAGE_DIR, name=codepage_name).splitlines():
        # ignore empty lines and comment lines (first char is #)
        if (not line) or (line[0] == '#'):
            continue
        # strip off comments; split unicodepoint and hex string
        splitline = line.split('#')[0].split(':')
        # ignore malformed lines
        if len(splitline) < 2:
            continue
        try:
            # extract codepage point
            cp_point = splitline[0].strip().decode('hex')
            # allow sequence of code points separated by commas
            grapheme_cluster = u''.join(unichr(int(ucs_str.strip(), 16)) for ucs_str in splitline[1].split(','))
            codepage[cp_point] = grapheme_cluster
        except (ValueError, TypeError):
            logging.warning('Could not parse line in codepage file: %s', repr(line))
    return codepage
