10 ' test frame - store program lines 65530 or higher
20 ON ERROR GOTO 100
25 OPEN "errors.txt" FOR OUTPUT AS 1
30 STOP
100 PRINT#1, "error "; ERR; " in "; ERL
110 RESUME
65529 '
