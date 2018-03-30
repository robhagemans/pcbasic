#!/usr/bin/env python2
from lxml import etree, html
import re
from cStringIO import StringIO
import gzip
import os
from os import path
from codecs import open


# obtain metadata without importing the package (to avoid breaking setup)
with open(
        path.join(path.abspath(path.dirname(__file__)), '..', 'pcbasic', 'metadata.py'),
        encoding='utf-8') as f:
    exec(f.read())

basepath = os.path.dirname(os.path.realpath(__file__))


def html_to_man(html):
    def massage(text):
        return re.sub(' +', ' ', text.encode('utf-8').replace('\\', '\\[rs]').replace('-', '\\-').replace('|', '\\||').replace('.', '\\|.').replace('\n', ' ').replace('"', '\\[dq]').replace("'", "\\|'"))

    def convert_html(e, indent=0, inside=False):
        inner = massage(e.text) if e.text else ''
        tail = massage(e.tail) if e.tail else ''
        children = ''.join(convert_html(child, 1+indent, inside or e.tag.upper()=='DD') for child in e.iterchildren(tag=etree.Element))
        if e.tag.upper() == 'H1':
            return '\n.SH NAME\n' + inner.lower().replace('\-', '') + ' \- '
        elif e.tag.upper() in ('H2', 'H3'):
            return '\n.SH ' + inner.upper() + children.upper() + '\n' + tail
        elif e.tag.upper() in ('VAR', 'I'):
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


def makeman():
    title_html = '<h1>pcbasic</h1><p>%s</p>\n' % DESCRIPTION
    desc_html = '<h3>Description</h2><p>%s</p>\n' % LONG_DESCRIPTION
    options_html = open(basepath + '/options.html', mode='r').read()
    examples_html = open(basepath + '/examples.html', mode='r').read()
    more_html = open(basepath + '/moreman.html', mode='r').read()
    man_html = title_html + desc_html + options_html + examples_html + more_html
    try:
        os.mkdir(basepath + '/../doc')
    except OSError:
        # already there, ignore
        pass
    # output manfile
    with gzip.open(basepath + '/../doc/pcbasic.1.gz', 'wb') as manfile:
        manfile.write(html_to_man(man_html))

if __name__ == '__main__':
    makeman()
