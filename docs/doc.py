"""
PC-BASIC - docs.doc
HTML documentation builder

(c) 2013--2022 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

import os
import json
from datetime import datetime
from io import StringIO, open

from lxml import etree
import markdown
from markdown.extensions.toc import TocExtension, slugify

from pcbasic.basic import VERSION


BASEPATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(BASEPATH, 'description.json'), encoding='utf-8') as desc_json:
    DESCR_STRS = json.load(desc_json)


def read_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return f.read()


def _md_to_html(md_file, outf, prefix='', baselevel=1):
    """Convert markdown to html."""
    mdown = read_file(md_file)
    toc = TocExtension(
        baselevel=baselevel,
        slugify=(
            lambda value, separator:
            prefix + slugify(value, separator)
        )
    )
    outf.write(markdown.markdown(
        mdown, extensions=['markdown.extensions.tables', toc],
        output_format='html5', lazy_ol=False
    ))

def _maketoc(html_doc, toc):
    """Build table of contents."""
    parser = etree.HTMLParser()
    doc = etree.parse(html_doc, parser)
    last = -1
    toc.write(u'<nav class="toc">\n')
    toc.write(u'    <h2 id="toc">Table of Contents</h2>\n')
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
            toc.write(u'</li>\n')
            for i in range((last-level), 0, -1):
                toc.write(u'    '*((level+i-1)*2+1) + '</ul>\n')
                toc.write(u'    '*(level+i-1)*2 + '</li>\n')
        elif level-last > 0:
            toc.write(u'\n')
            for i in range(level-last, 0, -1):
                toc.write(u'    '*((level-i)*2+1) + '<ul>\n')
        else:
            toc.write(u'</li>\n')
        toc.write(u'    '*(level*2) + u'<li>' + etree.tostring(node).strip().decode('utf-8'))
        last = level
    toc.write(u'</li>\n')
    while level > first:
        toc.write(u'    '*(level*2-1) + '</ul>\n')
        level -= 1
    toc.write(u'</nav>\n')

def _embed_style(html_file):
    """Embed a CSS file in the HTML."""
    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(html_file, parser)
    for node in doc.xpath('//link[@rel="stylesheet"]'):
        href = node.get('href')
        css = os.path.join(BASEPATH, href)
        node.tag = 'style'
        node.text = '\n' + read_file(css) + '\n    '
        node.attrib.clear()
        node.set('id', href)
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(etree.tostring(doc, method="html").decode('utf-8'))

def _get_options(html_file):
    """Get the next command-line option."""
    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(html_file, parser)
    output = []
    for node in doc.xpath('//h3[@id="options"]/following-sibling::dl/dt/code'):
        node.tag = 'a'
        node.attrib.clear()
        link_id = node.getparent().get('id')
        if link_id:
            node.set('href', '#' + link_id)
            node.set('class', 'option-link')
            node.text = '[' + (node.text or '')
            try:
                last = node.getchildren()[-1]
                last.tail = (last.tail or '') + ']'
            except IndexError:
                node.text += ']'
            node.tail = '\n'
            output.append(node)
    return output

def _embed_options(html_file):
    """Build the synopsis of command-line options."""
    parser = etree.HTMLParser(encoding='utf-8')
    doc = etree.parse(html_file, parser)
    for node in doc.xpath('//span[@id="placeholder-options"]'):
        node.clear()
        node.extend(_option for _option in _get_options(html_file))
    with open(html_file, 'w', encoding='utf-8') as htmlf:
        htmlf.write(etree.tostring(doc, method='html').decode('utf-8'))

def makedoc(output_path, output_filename, *, header=None, embedded_style=True):
    """Build HTML documentation from sources."""
    header = header or BASEPATH + '/header.html'
    output = os.path.join(output_path, output_filename)
    try:
        os.mkdir(output_path)
    except OSError:
        # already there, ignore
        pass
    basic_license_stream = StringIO()
    doc_license_stream = StringIO()
    readme_stream = StringIO()
    ack_stream = StringIO()
    _md_to_html(BASEPATH + '/../LICENSE.md', basic_license_stream)
    _md_to_html(BASEPATH + '/LICENSE.md', doc_license_stream)
    _md_to_html(BASEPATH + '/../README.md', readme_stream, baselevel=0)
    _md_to_html(BASEPATH + '/../THANKS.md', ack_stream, 'acks_')

    # get the quick-start guide out of README
    quickstart = u''.join(readme_stream.getvalue().split(u'<hr>')[1:])
    quickstart = quickstart.replace(u'http://pc-basic.org/doc/2.0#', u'#')

    quickstart_html = ('<article>\n' + quickstart + '</article>\n')
    licenses_html = (
        '<footer>\n<h2 id="licence">Licences</h2>\n' + basic_license_stream.getvalue()
        + '<hr />\n' + doc_license_stream.getvalue() + '\n</footer>\n'
    )
    major_version = '.'.join(VERSION.split('.')[:2])
    settings_html = (
        '<article>\n'
        + read_file(BASEPATH + '/settings.html').replace('0.0', major_version)
        + '<hr />\n' + read_file(BASEPATH + '/options.html')
        + read_file(BASEPATH + '/examples.html') + '</article>\n'
    )
    predoc = StringIO()
    predoc.write(quickstart_html)
    predoc.write(read_file(BASEPATH + '/documentation.html'))
    predoc.write(settings_html)
    predoc.write(read_file(BASEPATH + '/guide.html'))
    predoc.write(read_file(BASEPATH + '/reference.html'))
    predoc.write(read_file(BASEPATH + '/techref.html'))
    predoc.write(read_file(BASEPATH + '/devguide.html'))
    predoc.write('<article>\n' + ack_stream.getvalue()  + '</article>\n')
    predoc.write(licenses_html)
    predoc.write(read_file(BASEPATH + '/footer.html'))
    predoc.seek(0)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if embedded_style:
        subheader_html = u"""
<header>
    <h1>PC-BASIC documentation</h1>
    <small>Version {0}</small>
</header>
""".format(VERSION)
    else:
        subheader_html = u''
    subheader_html += u"""
<article>
    <h2 id="top">PC-BASIC {0}</h2>
    <p>
        <em>{2}</em>
    </p>
    <p>
        {3}
    </p>
    <p>
        This is the documentation for <strong>PC-BASIC {0}</strong>, last updated <em>{1}</em>.<br />
        It consists of the following documents:
    </p>
    <ul>
        <li><strong><a href="#quick-start-guide">Quick Start Guide</a></strong>, the essentials needed to get started</li>
        <li><strong><a href="#using">User's Guide</a></strong>, in-depth guide to using the emulator</li>
        <li><strong><a href="#settings">Configuration Guide</a></strong>, settings and options</li>
        <li><strong><a href="#guide">Language Guide</a></a></strong>, overview of the BASIC language by topic</li>
        <li><strong><a href="#reference">Language Reference</a></strong>, comprehensive reference to BASIC</li>
        <li><strong><a href="#technical">Technical Reference</a></strong>, file formats and internals</li>
        <li><strong><a href="#dev">Developer's Guide</a></strong>, using PC-BASIC as a Python module</li>
    </ul>

""".format(VERSION, now, DESCR_STRS['description'], DESCR_STRS['long_description'])
    if not embedded_style:
        subheader_html += u"""
    <p>
        Offline versions of this documentation are available in the following formats:
    </p>
    <ul>
        <li><a href="PC-BASIC_documentation.html">Single-file HTML</a></li>
        <li><a href="PC-BASIC_documentation.pdf">PDF</a></li>
    </ul>
    <p>
        Documentation for other versions of PC-BASIC:
    </p>
    <ul>
        <li><a href="http://pc-basic.org/doc/1.2/">PC-BASIC 1.2</a></li>
    </ul>
</article>
"""
    else:
        subheader_html += u'</article>\n'
    tocdoc = StringIO()
    tocdoc.write(subheader_html)
    tocdoc.write(predoc.getvalue())
    tocdoc.seek(0)
    toc = StringIO()
    _maketoc(tocdoc, toc)
    header_html = read_file(header)
    with open(output, 'w', encoding='utf-8') as outf:
        outf.write(header_html)
        outf.write(subheader_html)
        outf.write(toc.getvalue())
        outf.write(predoc.getvalue())
    _embed_options(output)
    if embedded_style:
        _embed_style(output)
