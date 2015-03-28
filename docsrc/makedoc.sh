cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../data/USAGE
cat header.html description.html documentation.html options.html examples.html reference.html acknowledgements.html footer.html > ../doc/PC-BASIC_documentation.html
