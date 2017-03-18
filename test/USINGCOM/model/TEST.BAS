10 REM PC-BASIC test 
20 OPEN "OUTPUT" FOR OUTPUT AS 1
30 PRINT#1, USING "#######,.###"; 2000345.678
40 PRINT#1, USING "#######,.###"; 12345.678
50 PRINT#1, USING "#######,.###"; 345.678
60 PRINT#1, USING "#######,.####"; 205.6789
70 PRINT#1, USING "#######,.##########"; 1205.6789012
80 CLOSE
