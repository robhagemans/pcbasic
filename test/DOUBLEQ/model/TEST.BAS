10 REM PC-BASIC test 
20 REM Double equals sign should raise syntax error
30 OPEN "output" FOR OUTPUT AS 1
40 ON ERROR GOTO 200
50 PRINT#1, 1 == 2
60 CLOSE
70 END
200 PRINT#1, ERR, ERL
210 RESUME NEXT
