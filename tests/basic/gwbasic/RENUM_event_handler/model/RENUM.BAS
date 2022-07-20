10 ' test RENUMbering an active event handler 
20 ' we don't test if the event handling works
30 ' just the renumbering
40 ON KEY(1) GOSUB 70
50 KEY(1) ON
60 RENUM
70 ' event handler
80 RETURN
