#!/usr/bin/env python2
import sys
import os
import shutil
from cStringIO import StringIO
from datetime import datetime
import codecs

from lxml import etree
import markdown

basepath = os.path.dirname(os.path.realpath(__file__))

def mdtohtml(md_file, outf):
    with codecs.open(md_file, 'r', 'utf-8') as inf:
        md = inf.read()
        outf.write(markdown.markdown(md, extensions=['markdown.extensions.tables', 'markdown.extensions.toc'], output_format='html5', lazy_ol=False).encode('utf-8'))

def maketoc(html_doc, toc):
    parser = etree.HTMLParser()
    doc = etree.parse(html_doc, parser)
    last = -1
    toc.write('<nav class="toc">\n')
    toc.write('    <h2 id="toc">Table of Contents</h2>\n')
    for node in doc.xpath('//h2|//h3|//h4'):
        level = int(node.tag[1])
        node_id = node.get('id')
        if last == -1:
            last += level
            first = last
        node.tag = 'a'
        node.attrib.clear()
        if node_id:
            node.set('href', '#' + node_id)
        if level-last < 0:
            toc.write('</li>\n')
            for i in range((last-level), 0, -1):
                toc.write('    '*((level+i-1)*2+1) + '</ul>\n')
                toc.write('    '*(level+i-1)*2 + '</li>\n')
        elif level-last > 0:
            toc.write('\n')
            for i in range(level-last, 0, -1):
                toc.write('    '*((level-i)*2+1) + '<ul>\n')
        else:
            toc.write('</li>\n')
        toc.write('    '*(level*2) + '<li>' + etree.tostring(node).strip())
        last = level
    toc.write('</li>\n')
    while level > first:
        toc.write('    '*(level*2-1) + '</ul>\n')
        level -= 1
    toc.write('</nav>\n')


def makedoc(header=None, output=None):
    header = header or basepath + '/header.html'
    output = output or basepath + '/../doc/PC-BASIC_documentation.html'
    try:
        os.mkdir(basepath + '/../doc')
    except OSError:
        # already there, ignore
        pass
    shutil.copy(basepath + '/doc.css', basepath + '/../doc/')
    shutil.copy(basepath + '/LICENSE.md', basepath + '/../doc/')
    basic_license_stream = StringIO()
    doc_license_stream = StringIO()
    readme_stream = StringIO()
    mdtohtml(basepath + '/../LICENSE.md', basic_license_stream)
    mdtohtml(basepath + '/LICENSE.md', doc_license_stream)
    mdtohtml(basepath + '/../README.md', readme_stream)
    quickstart_html = ('<article>\n' + readme_stream.getvalue() + '</article>\n').replace('h3', 'h2').replace('h4', 'h3').replace('PC-BASIC</h2>', 'Overview</h2>')
    licenses_html = '<footer>\n<h2 id="licence">Licences</h2>\n' + basic_license_stream.getvalue() + '<hr />\n' + doc_license_stream.getvalue() + '\n</footer>\n'
    settings_html = ('<article>\n' + open(basepath + '/settings.html', 'r').read()
            + '<hr />\n' + open(basepath + '/options.html', 'r').read()
            + open(basepath + '/examples.html', 'r').read() + '</article>\n')
    predoc = StringIO()
    predoc.write(quickstart_html)
    predoc.write(open(basepath + '/documentation.html', 'r').read())
    predoc.write(settings_html)
    predoc.write(open(basepath + '/reference.html', 'r').read())
    predoc.write(open(basepath + '/techref.html', 'r').read())
    predoc.write(open(basepath + '/acknowledgements.html', 'r').read())
    predoc.write(licenses_html)
    predoc.write(open(basepath + '/footer.html', 'r').read())
    predoc.seek(0)
    toc = StringIO()
    maketoc(predoc, toc)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    version = open(basepath + '/../pcbasic/data/version.txt', 'r').read().strip()
    subheader_html = '<header>\n<h1>PC-BASIC {0} documentation</h1>\n<small>Documentation compiled on {1}.</small>\n</header>\n'.format(version, now)
    with open(output, 'w') as outf:
        outf.write(open(header, 'r').read())
        outf.write(subheader_html)
        outf.write(toc.getvalue())
        outf.write(predoc.getvalue())

if __name__ == '__main__':
    header, output = None, None
    try:
        header = sys.argv[1]
        output = sys.argv[2]
    except IndexError:
        pass
    makedoc(header, output)
