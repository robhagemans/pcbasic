10 REM PC-BASIC test
20 REM numeric literals and expressions
25 OPEN "literals.dat" FOR OUTPUT AS 1
30 PRINT#1, &O 7
40 PRINT#1, -&-1
50 PRINT#1, -&H-1
60 PRINT#1, 7 &---77
60 PRINT#1, 7 ---&77
70 PRINT#1, &-77
80 PRINT#1, -&77
90 CLOSE
100 SAVE"LIT2.ASC",A

