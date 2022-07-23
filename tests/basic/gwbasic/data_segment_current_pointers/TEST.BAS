10 A=1:ABC=2:LONG.NAME=3:VERY.LONG.VARIABLE.NAME=4
15 DIM B(3):B(0)=1:B(1)=2:B(3)=3
20 DEF SEG
21 OPEN "memdump.txt" FOR OUTPUT AS 1
22 ' addresses shift as they are defined
25 PRINT#1,  "program: ";: PROG = PEEK(&H30) + PEEK(&H31)*256: PRINT#1, PROG
30 PRINT#1,  "scalars: ";: SCAL = PEEK(&H358) + PEEK(&H359)*256: PRINT#1, SCAL
40 PRINT#1,  "arrays : ";: ARRY = PEEK(&H35A) + PEEK(&H35B)*256: PRINT#1, ARRY
50 PRINT#1,  "end arr: ";: ENDA = PEEK(&H35C) + PEEK(&H35D)*256: PRINT#1, ENDA
50 PRINT#1,  "total  : ";: TOTL = PEEK(&H2C) + PEEK(&H2D)*256: PRINT#1, TOTL
999 CLOSE: END

