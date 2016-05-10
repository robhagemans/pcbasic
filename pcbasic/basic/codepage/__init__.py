"""
PC-BASIC - codepage package
Codepage definitions

(c) 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import pkgutil

codepages = (
    '1258', '437', '720', '737', '775', '806', '850', '851', '852', '853',
    '855', '856', '857', '858', '860', '861', '862', '863', '864', '865',
    '866', '868', '869', '874', '932', '934', '936', '938', '949', '950',
    'alternativnyj', 'armscii8a', 'big5-2003', 'big5-hkscs', 'georgian-academy',
    'georgian-ps', 'iransystem', 'iscii-as', 'iscii-be', 'iscii-de', 'iscii-gu',
    'iscii-ka', 'iscii-ma', 'iscii-or', 'iscii-pa', 'iscii-ta', 'iscii-te',
    'kamenicky', 'koi8-r', 'koi8-ru', 'koi8-u', 'mazovia', 'mik', 'osnovnoj',
    'pascii', 'ruscii', 'russup3', 'russup4ac', 'russup4na', 'viscii')


class ResourceFailed(Exception):
    """Failed to load codepage."""
    def __str__(self):
        return self.__doc__


def read_file(codepage_name):
    """Retrieve contents of codepage file."""
    try:
        resource = pkgutil.get_data(__name__, codepage_name + '.ucp')
    except EnvironmentError:
        raise ResourceFailed()
    if resource is None:
        raise ResourceFailed()
    return resource
