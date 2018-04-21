10 open "output.txt" for output as 1
15 on error goto 100
20 print#1, val("")
21 print#1, val(chr$(0))
22 print#1, val(chr$(&h1c))
23 print#1, val(chr$(&h1d))
24 print#1, val(chr$(&h1e))
30 print#1, "end"
40 end
100 print#1, "error", err, erl
110 resume next

