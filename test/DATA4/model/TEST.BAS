10 REM PC-BASIC test 
20 REM DATA and IF
30 DATA one, two, three, four
40 IF 0 THEN DATA five, six: DATA seven ELSE DATA eight: DATA nine, ten
50 DATA eleven, twelve, thirteen, fourteen, fifteen, sixteen
60 OPEN "output.txt" FOR OUTPUT AS 1
70 FOR I = 1 TO 10
80 READ A$: PRINT#1, "[" A$ "]"
90 NEXT
100 CLOSE


