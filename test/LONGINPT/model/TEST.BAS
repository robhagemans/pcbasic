10 REM PC-BASIC test for long input lines
20 REM 
30 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 INPUT "Example of what happens when the INPUT line is more than 80 characters long 12345678 ",Z$
50 PRINT#1, "Z$="Z$
