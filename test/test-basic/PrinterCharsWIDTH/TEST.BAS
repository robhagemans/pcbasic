5 OPEN "output.txt" for output as 1
6 open "lpt1:" for output as 2
7 WIDTH#2, 40
10 for c = 0 to 255
20 PRINT#2, chr$(c);:PRINT#1, i, LPOS(0)
30 next

