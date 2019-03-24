10 ' test nested loops with variables and commas in NEXT
20 open "output.txt" for output as 1
30 for i=1 to 2
40 for j=1 to 3
50 for k=1 to 5
60 print#1, i, j, k
70 next k, j
80 print#1, "outer"
90 next i

