10 ' test INPUT on existing wrapping line of text 
20 CLS: LOCATE 10,1: PRINT STRING$(100, "#")
30 LOCATE 10, 1: INPUT "prompt"; A$
40 open "output.txt" for output as 1
50 print#1, a$
60 close

