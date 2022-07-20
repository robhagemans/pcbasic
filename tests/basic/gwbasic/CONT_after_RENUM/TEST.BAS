1 ' test STOP/CONT with RENUM in between
30 OPEN "output.txt" for output as #1
50 PRINT#1, 1
51 STOP
70 PRINT#1, 2
90 CLOSE

