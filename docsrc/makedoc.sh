#!/bin/bash
# create documentation
if [ -e $1 ]
then
  HEADER=pc-basic/docsrc/header.html
else
  HEADER=$1
fi
if [ -e $2 ]
then
   OUTPUT=pc-basic/doc/PC-BASIC_documentation.html
else
   OUTPUT=$2
fi
echo $HEADER $OUTPUT
pandoc ../README.md -t html5 -o readme.html
(echo "<article>"; cat readme.html; echo "</article>") | sed -e "s/h3/h1/g" -e "s/h4/h2/g" -e "s_PC-BASIC</h1>_Overview</h1>_"> readme2.html
mkdir ../doc
cp doc.css ../doc
cp LICENSE.md ../doc
pandoc ../LICENSE.md -t html5 -o pcbasiclicense.html
pandoc LICENSE.md -t html5 -o doclicense.html

(echo "<footer><h1 id=\"licence\">Licences</h1>"; cat pcbasiclicense.html doclicense.html; echo "</footer>") > licences.html
(cat readme2.html documentation.html; echo -e "<article>\n<h1 id=\"invocation\">Invocation</h1>"; cat options.html examples.html; echo "</article>"; cat reference.html acknowledgements.html licences.html footer.html) > predoc.html
./maketoc.py predoc.html > toc.html
echo -e "<header>\n<h1>PC-BASIC $(cat ../pcbasic/data/version.txt) documentation</h1>\n<small>Documentation compiled on $(date --utc).</small>\n</header>" > subheader.html
(cat ../../$HEADER subheader.html toc.html predoc.html) > ../../$OUTPUT
rm predoc.html toc.html description.html readme.html readme2.html subheader.html pcbasiclicense.html doclicense.html licences.html
