5 open "output.txt" for output as 1
10 def fna(x) = x + fna(x)
15 on error goto 100
20 print#1, fna(2)
30 print#1, "end"
40 end
100 print#1, "error", err, erl
110 resume next

