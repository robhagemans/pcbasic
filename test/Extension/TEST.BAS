10 REM PC-BASIC test 
20 REM Python extension test
30 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 A = 1
50 B = _ADD(A, 1)
60 PRINT#1, A, B
70 _OUTPUT "one", 2, 3!, 4#
80 _OUTPUT "!œ$"
90 PRINT#1, "<end>"

