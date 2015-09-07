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
mkdir ../doc
cp doc.css ../doc
cp LICENSE.md ../doc
./mdtohtml.py ../LICENSE.md pcbasiclicense.html
./mdtohtml.py LICENSE.md doclicense.html

(echo "<article>"; ./mdtohtml.py ../README.md /dev/stdout; echo "</article>") | sed -e "s/h3/h1/g" -e "s/h4/h2/g" -e "s_PC-BASIC</h1>_Overview</h1>_"> quickstart.html
(echo -e "<footer>\n<h1 id=\"licence\">Licences</h1>"; cat pcbasiclicense.html doclicense.html; echo "</footer>") > licences.html
(echo -e "<article>"; cat settings.html options.html examples.html; echo "</article>") > settings-options.html
(cat quickstart.html documentation.html settings-options.html reference.html techref.html acknowledgements.html licences.html footer.html) > predoc.html
./maketoc.py predoc.html > toc.html
echo -e "<header>\n<h1>PC-BASIC $(cat ../pcbasic/data/version.txt) documentation</h1>\n<small>Documentation compiled on $(date --utc).</small>\n</header>" > subheader.html
(cat ../../$HEADER subheader.html toc.html predoc.html) > ../../$OUTPUT
rm predoc.html toc.html quickstart.html subheader.html pcbasiclicense.html doclicense.html licences.html settings-options.html
