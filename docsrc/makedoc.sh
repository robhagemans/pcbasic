cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../data/USAGE
cat documentation.html options.html examples.html reference.html acknowledgements.html footer.html > predoc.html
./maketoc.py predoc.html > toc.html
(cat header.html description.html; echo -n "<small>PC-BASIC "; cat ../data/VERSION; echo -n "&mdash; documentation compiled on "; date --utc; echo "</small>"; cat toc.html predoc.html) > ../doc/PC-BASIC_documentation.html
rm predoc.html
