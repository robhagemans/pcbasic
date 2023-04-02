"""
PC-BASIC - docs.man
Manfile builder

(c) 2013--2023 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import re
import json
import gzip
from io import StringIO

from lxml import etree


# file locations
SOURCE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'source')
OPTIONS_HTML = os.path.join(SOURCE_PATH, 'options.html')
EXAMPLE_HTML = os.path.join(SOURCE_PATH, 'examples.html')
MORE_HTML = os.path.join(SOURCE_PATH, 'moreman.html')

# long and short descriptions
with open(os.path.join(SOURCE_PATH, 'description.json'), encoding='utf-8') as desc_json:
    DESC_STRS = json.load(desc_json)


def make_man(man_path, man_name):
    """Convert HTML sources to manfile."""
    title_html = '<h1>pcbasic</h1><p>%s</p>\n' % DESC_STRS['description']
    desc_html = '<h3>Description</h2><p>%s</p>\n' % DESC_STRS['long_description']
    options_html = open(OPTIONS_HTML).read()
    examples_html = open(EXAMPLE_HTML).read()
    more_html = open(MORE_HTML).read()
    man_html = ''.join((title_html, desc_html, options_html, examples_html, more_html))
    # output manfile
    man_file = os.path.join(man_path, man_name)
    with gzip.open(man_file, 'w') as man:
        man.write(_html_to_man(man_html).encode('utf-8'))


def _text_to_man(text):
    """Convert plain text to troff."""
    # escape special characters
    troff_escapes = [
        (u'\\', u'\\[rs]'), (u'-', u'\\-'), (u'|', u'\\||'),
        (u'.', u'\\|.'), (u'"', u'\\[dq]'), (u"'", u"\\|'"),
    ]
    for key, value in troff_escapes:
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
