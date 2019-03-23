10 ' test PRINTing to RANDOM file
20 OPEN "output.dat" FOR RANDOM AS 1
30 FIELD#1, 20 as A$, 20 as b$
40 LSET b$="abcde"
50 PRINT#1, 1234
60 PUT#1, 1
65 CLOSE
70 OPEN "output.txt" FOR OUTPUT AS 1
80 OPEN "output.dat" FOR RANDOM AS 2
90 FIELD#2, 20 as A$, 20 as b$
100 GET#2, 1
110 WRITE#1, A$, B$
120 CLOSE

