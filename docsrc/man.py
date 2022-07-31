"""
PC-BASIC - docsrc.man
Manfile builder

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import re
import json
import gzip
from io import StringIO, open

from lxml import etree


# file locations
BASEPATH = os.path.dirname(os.path.realpath(__file__))
OPTIONS_HTML = os.path.join(BASEPATH, 'options.html')
EXAMPLE_HTML = os.path.join(BASEPATH, 'examples.html')
MORE_HTML = os.path.join(BASEPATH, 'moreman.html')
DOC_PATH = os.path.join(BASEPATH, '..', 'doc')
MAN_FILE = os.path.join(BASEPATH, '..', 'doc', 'pcbasic.1.gz')

# setup metadata
with open(os.path.join(BASEPATH, 'description.json'), encoding='utf-8') as desc_json:
    DESC_STRS = json.load(desc_json)


TROFF_ESCAPES = [
    (u'\\', u'\\[rs]'), (u'-', u'\\-'), (u'|', u'\\||'),
    (u'.', u'\\|.'), (u'"', u'\\[dq]'), (u"'", u"\\|'"),
]


def _text_to_man(text):
    """Convert plain text to troff."""
    # escape special characters
    for key, value in TROFF_ESCAPES:
        text = text.replace(key, value)
    # replace line feeds with spaces
    text = text.replace(u'\n', u' ')
    # replace repeated spaces with a single space
    text = re.sub(u' +', u' ', text)
    return text

def _convert_element(element, indent=0, inside=False):
    """Recursively convert HTML element to troff."""
    inner = _text_to_man(element.text) if element.text else ''
    tail = _text_to_man(element.tail) if element.tail else ''
    tag = element.tag.upper()
    children = ''.join(
        _convert_element(child, 1+indent, inside or tag == 'DD')
        for child in element.iterchildren(tag=etree.Element)
    )
    if tag == 'H1':
        return '\n.SH NAME\n' + inner.lower().replace('\\-', '') + ' \\- '
    if tag in ('H2', 'H3'):
        return '\n.SH ' + inner.upper() + children.upper() + '\n' + tail
    if tag in ('VAR', 'I'):
        return '\\fI' + inner + children + '\\fR' + tail
    if tag == 'B':
        return '\\fB' + inner + children + '\\fR' + tail
    if tag == 'DT':
        if inside:
            return '\n\n'+ inner + children + '\t' + tail
        return '\n.IP "' + inner + children + '"\n' + tail
    if tag == 'P':
        return '\n'+ inner + children + '\n' +tail
    if tag in ('DD', 'DL'):
        return inner + children + '\n' +tail
    return inner + children + tail

def _html_to_man(html):
    """Convert HTML to troff."""
    doc = etree.parse(StringIO(html), etree.HTMLParser(encoding='utf-8'))
    docroot = doc.getroot()
    manpage = '\'\\" t\n.pc\n.TH PCBASIC 1\n' + _convert_element(docroot)
    # replace two starting spaces (not sure where from)
    return re.sub('\t +', '\t', re.sub('\n +', '\n', manpage))


def makeman():
    """Convert HTML sources to manfile."""
    title_html = '<h1>pcbasic</h1><p>%s</p>\n' % DESC_STRS['description']
    desc_html = '<h3>Description</h2><p>%s</p>\n' % DESC_STRS['long_description']
    options_html = open(OPTIONS_HTML).read()
    examples_html = open(EXAMPLE_HTML).read()
    more_html = open(MORE_HTML).read()
    man_html = ''.join((title_html, desc_html, options_html, examples_html, more_html))
    try:
        os.mkdir(DOC_PATH)
    except EnvironmentError:
        # already there, ignore
        pass
    # output manfile
    with gzip.open(MAN_FILE, 'w') as manfile:
        manfile.write(_html_to_man(man_html).encode('utf-8'))
