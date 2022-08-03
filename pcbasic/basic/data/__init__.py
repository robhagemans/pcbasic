"""
PC-BASIC - data

(c) 2021--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from ...compat import resources
import json

# copyright metadata
_METADATA = json.loads(resources.read_binary(__package__, 'meta.json'))
NAME, VERSION, AUTHOR, COPYRIGHT = (_METADATA[_key] for _key in (
    'name', 'version', 'author', 'copyright'
))

# release metadata, if available
try:
    _RELEASE_ID = json.loads(resources.read_binary(__package__, 'release.json'))
except EnvironmentError:
    _RELEASE_ID = {u'tag': u'', u'commit': u'unreleased', u'timestamp': u''}
TAG, TIMESTAMP, COMMIT = (_RELEASE_ID[_key] for _key in (u'tag', u'timestamp', u'commit'))
if COMMIT in TAG: # pragma: no cover
    LONG_VERSION = u'%s [%s %s]' % (VERSION, TAG, TIMESTAMP)
else: # pragma: no cover
    LONG_VERSION = u'%s [%s %s %s]' % (VERSION, TAG, COMMIT, TIMESTAMP)

# default font and codepage
DEFAULT_FONT = tuple(json.loads(resources.read_binary(__package__, 'font.json')))
DEFAULT_CODEPAGE = tuple(json.loads(resources.read_binary(__package__, 'codepage.json')))
