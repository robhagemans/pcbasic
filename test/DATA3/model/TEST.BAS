10 REM PC-BASIC test 
20 REM DATA and remarks
30 DATA one, two, three 'four
40 DATA five, six: REM seven: DATA eight
50 DATA nine, ten, eleven, twelve
60 OPEN "output.txt" FOR OUTPUT AS 1
70 FOR I = 1 TO 8
80 READ A$: PRINT#1, "[" A$ "]"
90 NEXT
100 CLOSE


