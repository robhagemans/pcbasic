10 open "output.txt" for output as 1
15 on error goto 100
20 print#1, string$(7)
30 print#1, "end"
40 end
100 print#1, "error", err, erl
110 resume next

