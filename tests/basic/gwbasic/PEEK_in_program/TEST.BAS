1 ' PEEK into the program
5 OPEN "output.txt" FOR OUTPUT AS 1
10 GOSUB 100
20 A=VARPTR(A$)
30 PRINT#1, A, PEEK(A), PEEK(A+1), PEEK(A+2),
40 S=256*PEEK(A+2)+PEEK(A+1)
45 PRINT#1, S
50 FOR I = S TO S+20:PRINT#1, PEEK(I);:NEXT
60 CLOSE
70 END
100 A$="1":RETURN

