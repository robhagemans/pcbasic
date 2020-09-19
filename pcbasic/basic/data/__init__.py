"""
PC-BASIC - data

(c) 2020 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

from pkg_resources import resource_string
import json

_METADATA = json.loads(resource_string(__name__, 'meta.json'))
NAME, VERSION, AUTHOR, COPYRIGHT = (_METADATA[_key] for _key in (
    'name', 'version', 'author', 'copyright'
))

try:
    _RELEASE_ID = json.loads(resource_string(__name__, 'release.json'))
except EnvironmentError:
    _RELEASE_ID = {u'tag': u'', u'commit': u'unreleased', u'timestamp': u''}
TAG, TIMESTAMP, COMMIT = (_RELEASE_ID[_key] for _key in (u'tag', u'timestamp', u'commit'))
if COMMIT in TAG: # pragma: no cover
    LONG_VERSION = u'%s [%s %s]' % (VERSION, TAG, TIMESTAMP)
else: # pragma: no cover
    LONG_VERSION = u'%s [%s %s %s]' % (VERSION, TAG, COMMIT, TIMESTAMP)
