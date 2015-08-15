cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../data/USAGE
cat documentation.html options.html examples.html reference.html acknowledgements.html footer.html > predoc.html
./maketoc.py predoc.html > toc.html
(cat header.html; echo -e "<h1>PC-BASIC $(cat ../data/VERSION)</h1>\n<p><small>Documentation compiled on $(date --utc).</small></p>"; cat toc.html predoc.html) > ../doc/PC-BASIC_documentation.html
rm predoc.html toc.html
