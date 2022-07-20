0 ' rem line 0
1 ' rem line 1
5 ' rem line 5
10 ' test RENUMbering an error handler 
11 ' we don't test if the error handling works
12 ' just the renumbering
20 on error goto 100
21 rem
30 renum
40 on error goto 0' this is not really line 0
100 ' event handler
120 resume 20

