#!/bin/sh
pandoc ../DESCRIPTION.md -o description.html
cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../pcbasic/data/usage.txt
mkdir ../doc
cp doc.css ../doc
cp LICENSE.md ../doc
(cat documentation.html; echo "<article>\n<h1 id=\"invocation\">Invocation</h1>"; cat options.html examples.html; echo "</article>"; cat reference.html acknowledgements.html footer.html) > predoc.html
./maketoc.py predoc.html > toc.html
(cat header.html; echo "<header>\n<h1>PC-BASIC $(cat ../pcbasic/data/version.txt)</h1>\n<p><small>Documentation compiled on $(date --utc).</small></p></header>"; cat toc.html predoc.html) > ../doc/PC-BASIC_documentation.html
rm predoc.html toc.html description.html
