"""
PC-BASIC - docs.usage
Usage textfile builder

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import re
import textwrap
from io import StringIO

from lxml import etree


# file locations
BASEPATH = os.path.dirname(os.path.realpath(__file__))
INPUT_HTML = os.path.join(BASEPATH, 'options.html')


def make_usage(output_path, output_name):
    """Build USAGE.txt file."""
    output_file = os.path.join(output_path, output_name)
    with open(INPUT_HTML, mode='r', encoding='utf-8') as html_file:
        with open(output_file, 'w', encoding='utf-8') as textfile:
            textfile.write(_html_to_text(html_file.read()))


class TextBlock(object):
    """Block of text with minimal formatting."""

    def __init__(self, indent=0, content='', break_after=0):
        """Cteate block of text."""
        self.indent = indent
        self.content = content
        self.break_after = break_after

    def __str__(self):
        """Convert to str."""
        content = re.sub(' +', ' ', self.content.replace('\n', ' ')).strip()
        block = (
            '\t' * self.indent
            + ('\n' + '\t'*self.indent).join(textwrap.wrap(content, replace_whitespace=False))
        )
        return block + '\n' * self.break_after


# html tags to plaintext formatting
INDENT_TAGS = u'DD',
BLOCK_TAGS = u'P', u'H1', u'H2', u'H3', u'DT'
BREAK_AFTER_TAGS = u'DD', u'P', u'H1', u'H2', u'H3'
UPPER_TAGS = u'H1', u'H2', u'H3'


def _parse_element(element, blocklist=None):
    """Recursively parse an element of the document tree."""
    if not blocklist:
        blocklist = [TextBlock()]
    last_indent = blocklist[-1].indent
    tag = element.tag.upper()
    inner = element.text if element.text else ''
    tail = element.tail if element.tail else ''
    if tag in UPPER_TAGS:
        inner = inner.upper()
    break_after = (tag in BREAK_AFTER_TAGS or element.get('class') == 'block')
    if tag in BLOCK_TAGS or element.get('class') == 'block':
        blocklist.append(TextBlock(last_indent, '', break_after))
    elif tag in INDENT_TAGS:
        blocklist.append(TextBlock(last_indent+1, '', break_after))
    blocklist[-1].content += inner
    for child in element.iterchildren(tag=etree.Element):
        blocklist = _parse_element(child, blocklist)
    if (tag in INDENT_TAGS + BLOCK_TAGS or blocklist[-1].indent != last_indent):
        break_after = blocklist[-1].break_after
        blocklist.append(TextBlock(last_indent, tail, break_after))
    else:
        blocklist[-1].content += tail
    return blocklist

def _html_to_text(html):
    """Extract plain text from HTML."""
    doc = etree.parse(StringIO(html), etree.HTMLParser(encoding='utf-8'))
    blocklist = _parse_element(doc.getroot())
    return u'\n'.join(str(block) for block in blocklist[1:] if str(block).strip())
