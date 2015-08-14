cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../data/USAGE
(cat header.html description.html; echo -n "<small>PC-BASIC "; cat ../data/VERSION; echo -n "&mdash; documentation compiled on "; date --utc; echo "</small>"; cat documentation.html options.html examples.html reference.html acknowledgements.html footer.html) > ../doc/PC-BASIC_documentation.html
