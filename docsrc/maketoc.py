#!/usr/bin/env python2
from lxml import etree
import sys

def maketoc(html_doc, tocfile):
    parser = etree.HTMLParser()
    doc = etree.parse(html_doc, parser)
    toc = open(tocfile, 'w')
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

if __name__ == '__main__':
    maketoc(sys.argv[1], sys.argv[2])
