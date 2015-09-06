#!/usr/bin/env python2
from lxml import etree, html
import codecs
import sys
import re
from cStringIO import StringIO
import subprocess
import time
import os


def massage(text):
    return re.sub(' +', ' ', text.encode('utf-8').replace('\\', '\\\\').replace('-', '\\-').replace('|', '\\||').replace('.', '\\|.').replace('\n', ' '))

def html_to_text(e, indent='', inside=False):
    inner = massage(e.text) if e.text else ''
    tail = massage(e.tail) if e.tail else ''
    #sys.stderr.write(indent + e.tag.upper())
    #if inner:
    #    sys.stderr.write( ' inner "%s"' % inner )
    #if tail:
    #    sys.stderr.write( ' tail "%s"' % tail )
    #sys.stderr.write( '\n')
    children = ''.join(html_to_text(child, '  '+indent, inside or e.tag.upper()=='DD') for child in e.iterchildren(tag=etree.Element))
    if e.tag.upper() == 'H1':
        return '\n.SH NAME\n' + inner.lower().replace('\-', '') + ' \- '
    elif e.tag.upper() == 'H2':
        return '\n.SH ' + inner.upper() + children.upper() + '\n' + tail
    elif e.tag.upper() == 'VAR':
        return '\\fI' + inner + children + '\\fR' + tail
    elif e.tag.upper() == 'B':
        return '\\fB' + inner + children + '\\fR' + tail
    elif e.tag.upper() == 'DT':
        if inside:
            return '\n\n'+ inner + children + '\t' + tail
        else:
            return '\n.IP "' + inner + children + '"\n' + tail
    elif e.tag.upper() == 'P':
        return '\n'+ inner + children + '\n' +tail
    elif e.tag.upper() == 'DD':
        return inner + children + '\n' +tail
    elif e.tag.upper() == 'DL':
        return inner + children + '\n' +tail
    else:
        return inner + children + tail

def html_to_man(html):
    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(StringIO(html), parser)
    docroot = doc.getroot()
    manpage = '\'\\" t\n.pc\n.TH PCBASIC 1\n' + html_to_text(docroot)
    # replace two starting spaces (not sure where from)
    return re.sub('\t +', '\t', re.sub('\n +', '\n', manpage))


title_html = '<h1>pcbasic</h1><p>%s</p>\n' % open('tagline.txt', mode='r').read()
desc_html = '<h2>Description</h2><p>%s</p>\n' % open('description.txt', mode='r').read()
options_html = open('options.html', mode='r').read()
examples_html = open('examples.html', mode='r').read()
man_html = title_html + desc_html + options_html + examples_html
usage_html = options_html

# output manfile
with open('../doc/pcbasic.1', 'w') as manfile:
    manfile.write(html_to_man(man_html))
subprocess.Popen('gzip -f ../doc/pcbasic.1'.split())

#print html_to_man(usage_html)
# output usage
with open('usage.man', 'w') as manfile:
    manfile.write(html_to_man(usage_html))

# constructing the pipes through popen seems to cut short the file some way or another
subprocess.call('cat usage.man | groff -t -e -mandoc -Tascii  | col -bx | tail -n +5 | head -n -5 > ../pcbasic/data/usage.txt', shell=True)
os.remove('usage.man')
