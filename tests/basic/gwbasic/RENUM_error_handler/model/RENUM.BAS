10  ' rem line 0
20 ' rem line 1
30 ' rem line 5
40 ' test RENUMbering an error handler 
50 ' we don't test if the error handling works
60 ' just the renumbering
70 ON ERROR GOTO 110
80 REM
90 RENUM
100 ON ERROR GOTO 0' this is not really line 0
110 ' event handler
120 RESUME 70
