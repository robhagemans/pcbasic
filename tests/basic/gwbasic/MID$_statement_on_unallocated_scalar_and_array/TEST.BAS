1 ' test MID$ statement on unallocated variable and array
10 DEF SEG: ON ERROR GOTO 200
20 OPEN "memtable.txt" FOR OUTPUT AS 1
25 PRINT#1, "start": GOSUB 100
29 ' these will raise IFC but allocate memory
30 MID$(A$, 1, 1) = "a"
35 PRINT#1, "after MID$(A$, 1, 1)": GOSUB 100
40 MID$(B$(1), 1, 1) = "a"
45 PRINT#1, "after MID$(B$(1), 1, 1)": GOSUB 100
99 CLOSE: END
100 ' write memory table
110 PROG=0: SCAL=0: ARRY=0: ENDA=0
120 PRINT#1,  "program: ";: PROG = PEEK(&H30) + PEEK(&H31)*256: PRINT#1, PROG
130 PRINT#1,  "scalars: ";: SCAL = PEEK(&H358) + PEEK(&H359)*256: PRINT#1, SCAL
140 PRINT#1,  "arrays : ";: ARRY = PEEK(&H35A) + PEEK(&H35B)*256: PRINT#1, ARRY
150 PRINT#1,  "end arr: ";: ENDA = PEEK(&H35C) + PEEK(&H35D)*256: PRINT#1, ENDA
160 RETURN
200 ' error trap
210 RESUME NEXT

