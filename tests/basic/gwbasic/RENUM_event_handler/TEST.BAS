10 ' test RENUMbering an active event handler 
11 ' we don't test if the event handling works
12 ' just the renumbering
20 on key(1) gosub 100
21 key(1) on
30 renum
100 ' event handler
120 return

