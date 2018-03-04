5 OPEN "output.txt" for output as 1
7 open "lpt1:" for output as #2
10 for c = 0 to 255
20 PRINT#2, chr$(c);:PRINT#1, i, LPOS(0)
30 next

