cat header.html description.html options.html footer.html | pandoc -f html -t plain > ../data/USAGE
(cat documentation.html; echo -e '<article>\n<h1 id="invocation">Invocation</h1>'; cat options.html examples.html; echo -e "</article>"; cat reference.html acknowledgements.html footer.html) > predoc.html
./maketoc.py predoc.html > toc.html
(cat header.html; echo -e "<header>\n<h1>PC-BASIC $(cat ../data/VERSION)</h1>\n<p><small>Documentation compiled on $(date --utc).</small></p></header>"; cat toc.html predoc.html) > ../doc/PC-BASIC_documentation.html
rm predoc.html toc.html
