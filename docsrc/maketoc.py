#!/usr/bin/env python2
from lxml import etree
import sys
parser = etree.HTMLParser()
doc = etree.parse(sys.argv[1], parser)
last = -1
print '<h2 id="toc">Table of Contents</h2>'
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
        print '</li>'
        print '    '*level + '</ul></li>\n'*(last-level),
    elif level-last > 0:
        print
        print '    '*last + '<ul>\n'*(level-last)
    else:
        print '</li>'
    print '    '*level + '<li>' + etree.tostring(node).strip(),
    last = level
print '</li>'
while level > first:
    level -= 1
    print '    '*level + '</ul>'
