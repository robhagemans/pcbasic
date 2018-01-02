5 OPEN "output.txt" FOR OUTPUT AS 1
10 DIM A$(2)
20 FOR I=1 TO 2
30   A$(I) = STR$(I) + STR$(I)
40 NEXT
50 B$ = "b"+"-string"
60 PRINT#1, FRE("")
70 ERASE A$
80 PRINT#1, FRE("")
