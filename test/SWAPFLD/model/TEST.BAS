10 OPEN "dummy" AS 1
15 OPEN "output.dat" FOR OUTPUT AS 2
20 FIELD#1, 20 AS A$
30 FIELD#1, 20 AS B$
40 LSET B$="aa"
50 C$="11
60 PRINT#2, A$, B$, C$
70 SWAP A$, C$
80 PRINT#2,  A$, B$, C$
90 LSET B$="bb
100 PRINT#2,  A$, B$, C$
110 CLOSE

