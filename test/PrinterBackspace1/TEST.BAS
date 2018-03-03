5 OPEN "output.txt" for output as 1
7 open "lpt1:" for output as 2
10 PRINT#2, "hi";:PRINT#1, lpos(0), lpos(1), lpos(2), lpos(3):PRINT#2,
20 PRINT#2, CHR$(8);"hi";:PRINT#1, lpos(0), lpos(1), lpos(2), lpos(3):PRINT#2,
30 PRINT#2, "hi";CHR$(8);"hi";:PRINT#1, lpos(0), lpos(1), lpos(2), lpos(3):PRINT#2,
40 PRINT#2, "hi";CHR$(8);:PRINT#1, lpos(0), lpos(1), lpos(2), lpos(3):PRINT#2,

