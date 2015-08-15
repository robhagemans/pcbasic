#!/usr/bin/env python2
from lxml import etree
import sys
parser = etree.HTMLParser()
doc = etree.parse(sys.argv[1], parser)
last = -1
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
    if level-last:
        print '    '*min(level, last) + '<ul>\n'*(level-last)+'</ul>\n'*(last-level),
    print '    '*level + '<li>' + etree.tostring(node).strip() + '</li>'
    last = level
while level > first:
    level -= 1
    print '    '*level + '</ul>'
    
