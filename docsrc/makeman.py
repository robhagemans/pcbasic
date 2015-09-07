#!/usr/bin/env python2
from lxml import etree, html
import codecs
import sys
import re
from cStringIO import StringIO
import subprocess
import time
import os
import gzip
import textwrap


def html_to_man(html):
    def massage(text):
        return re.sub(' +', ' ', text.encode('utf-8').replace('\\', '\\\\').replace('-', '\\-').replace('|', '\\||').replace('.', '\\|.').replace('\n', ' '))

    def convert_html(e, indent=0, inside=False):
        inner = massage(e.text) if e.text else ''
        tail = massage(e.tail) if e.tail else ''
        children = ''.join(convert_html(child, 1+indent, inside or e.tag.upper()=='DD') for child in e.iterchildren(tag=etree.Element))
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

    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(StringIO(html), parser)
    docroot = doc.getroot()
    manpage = '\'\\" t\n.pc\n.TH PCBASIC 1\n' + convert_html(docroot)
    # replace two starting spaces (not sure where from)
    return re.sub('\t +', '\t', re.sub('\n +', '\n', manpage))



def html_to_text(html):
    def massage(text):
        return re.sub(' +', ' ', text.replace('\n', ' '))

    def convert_html(e, indent=0, inside=False):
        inner = massage(e.text) if e.text else ''
        tail = massage(e.tail) if e.tail else ''
        children = ''.join(convert_html(child, 1+indent, inside or e.tag.upper()=='DD') for child in e.iterchildren(tag=etree.Element))
        if e.tag.upper() == 'H1':
            return ''
        elif e.tag.upper() == 'H2':
            text = ('\n'+'\t'*indent).join(textwrap.wrap((inner.upper() + children.upper()).strip(), replace_whitespace=False))
            return '\n' + '\t'*indent + text + '\n' + '\t'*indent + tail
        elif e.tag.upper() in ('P', 'DT'):
            text = ('\n' + '\t'*indent).join(textwrap.wrap((inner + children).strip(), replace_whitespace=False))
            return '\n' + '\t'*indent  + text + '\n' + '\t'*indent + tail
        elif e.tag.upper() == 'DD':
            text = ('\n' + '\t'*indent + '\t').join(textwrap.wrap((inner + children).strip(), replace_whitespace=False))
            return '\t'*indent + text + '\n' + '\t'*indent + tail
        elif e.tag.upper() == 'CODE' and e.get("class") == "block":
            text = ('\n'+'\t'*indent).join(textwrap.wrap((inner + children).strip(), replace_whitespace=False))
            return '\n' + '\t'*indent + text + '\n'+ '\t'*indent + tail
        #elif e.tag.upper() == 'DL':
        #    text = ('\n' + '\t'*indent).join(textwrap.wrap((inner + children).strip(), replace_whitespace=False))
        #    return '\n' + '\t'*indent + text + '\n' + tail
        else:
            return (inner + children + tail)

    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(StringIO(html), parser)
    docroot = doc.getroot()
    return convert_html(docroot, indent=-3)


title_html = '<h1>pcbasic</h1><p>%s</p>\n' % open('tagline.txt', mode='r').read()
desc_html = '<h2>Description</h2><p>%s</p>\n' % open('description.txt', mode='r').read()
options_html = open('options.html', mode='r').read()
examples_html = open('examples.html', mode='r').read()
man_html = title_html + desc_html + options_html + examples_html
usage_html = options_html

# output manfile
with gzip.open('../doc/pcbasic.1.gz', 'wb') as manfile:
    manfile.write(html_to_man(man_html))

# output usage
with codecs.open('usage.txt', 'w', 'utf-8') as textfile:
    textfile.write(html_to_text(usage_html))

# constructing the pipes through popen seems to cut short the file some way or another
#subprocess.call('cat usage.man | groff -t -e -mandoc -Tascii  | col -bx | tail -n +5 | head -n -5 > ../pcbasic/data/usage.txt', shell=True)
#os.remove('usage.man')
