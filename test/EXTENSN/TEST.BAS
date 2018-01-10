10 REM PC-BASIC test 
20 REM Python extension test
30 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 A = 1
50 B = _CALLP("add", A, 1)
60 PRINT#1, A, B
70 _CALLP "output", "one", 2, 3.0, 4#
80 _CALLP "output", "!£$"
90 PRINT#1, "<end>"
