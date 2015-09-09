#!/usr/bin/env python2
import markdown
import sys
import codecs

def mdtohtml(md_file, html_file):
    with codecs.open(md_file, 'r', 'utf-8') as inf:
        md = inf.read()
        with codecs.open(html_file, 'w', 'utf-8') as outf:
            outf.write(markdown.markdown(md, extensions=['markdown.extensions.tables', 'markdown.extensions.toc'], output_format='html5', lazy_ol=False))

if __name__ == '__main__':
    mdtohtml(sys.argv[1], sys.argv[2])
