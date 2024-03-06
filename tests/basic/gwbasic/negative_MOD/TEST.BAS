10 REM test for MOD with negative numbers (issue #231)
20 REM thanks https://github.com/tingtron https://github.com/GBR-613
30 OPEN "output.txt" FOR OUTPUT AS 1
40 PRINT#1, 17 MOD 3
50 PRINT#1, 17 MOD -3
60 PRINT#1, -17 MOD 3
70 PRINT#1, -17 MOD -3
80 CLOSE 1

