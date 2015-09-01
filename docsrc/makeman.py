#!/usr/bin/env python2
from lxml import etree, html
import sys
import re
#from cStringIO import StringIO

def massage(text):
    return re.sub(' +', ' ', text.encode('utf-8').replace('-', '\\-').replace('|', '\\||').replace('.', '\\|.').replace('\n', ' '))

def html_to_text(e, indent='', inside=False):
    inner = massage(e.text) if e.text else ''
    tail = massage(e.tail) if e.tail else ''
    sys.stderr.write(indent + e.tag.upper())
    if inner:
        sys.stderr.write( ' inner "%s"' % inner )
    if tail:
        sys.stderr.write( ' tail "%s"' % tail )
    sys.stderr.write( '\n')

    children = ''.join(html_to_text(child, '  '+indent, inside or e.tag.upper()=='DD') for child in e.iterchildren())

    if e.tag.upper() == 'H2':
        return '\n.SH ' + inner.upper() + children.upper() + '\n' + tail
    elif e.tag.upper() == 'VAR':
        return '\\fI' + inner + children + '\\fR' + tail
    elif e.tag.upper() == 'B':
        return '\\fB' + inner + children + '\\fR' + tail
    elif e.tag.upper() == 'DT':
        if inside:
            return '\n\n'+ inner + children + '\t' + tail
        else:
            return '\n.IP ' + inner + children + '\n' + tail
    elif e.tag.upper() == 'P':
        return '\n'+ inner + children + '\n' +tail
    elif e.tag.upper() == 'DD':
        return inner + children + '\n' +tail
    elif e.tag.upper() == 'DL':
        return inner + children + '\n' +tail
    else:
        return inner + children + tail

parser = etree.HTMLParser(encoding='utf-8')
doc = etree.parse(sys.argv[1], parser)
docroot = doc.getroot()
# replace two starting spaces (not sure where from)
print re.sub('\t +', '\t', re.sub('\n +', '\n', '\'\\" t\n.pc\n.TH PCBASIC 1\n'+html_to_text(docroot)))
