10 REM PC-BASIC test 
20 REM rounding double to single with overflow to exponent
25 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
30 X$ = chr$(255)+chr$(255)+chr$(255)+chr$(255)+chr$(255)+chr$(255)+chr$(127)+chr$(128) 
35 PRINT#1, cvd(x$)
40 PRINT#1, csng(cvd(x$))
50 A = cvd(x$): a$ = mks$(a)
60 FOR I%=1 TO 4
70 PRINT#1, hex$(asc(mid$(a$, i%))),
80 NEXT
