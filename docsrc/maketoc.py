#!/usr/bin/env python2
from lxml import etree
import sys
parser = etree.HTMLParser()
doc = etree.parse(sys.argv[1], parser)
last = -1
print '<nav class="toc">'
sys.stdout.write('    <h2 id="toc">Table of Contents</h2>')
for node in doc.xpath('//h1|//h2|//h3'):
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
        sys.stdout.write('</li>\n')
        for i in range((last-level), 0, -1):
            sys.stdout.write('    '*((level+i-1)*2+1) + '</ul>\n')
            sys.stdout.write('    '*(level+i-1)*2 + '</li>\n')
    elif level-last > 0:
        sys.stdout.write('\n')
        for i in range(level-last, 0, -1):
            print '    '*((level-i)*2+1) + '<ul>'
    else:
        sys.stdout.write('</li>\n')
    sys.stdout.write('    '*(level*2) + '<li>' + etree.tostring(node).strip())
    last = level
print '</li>'
while level > first:
    print '    '*(level*2-1) + '</ul>'
    level -= 1
print '</nav>'
