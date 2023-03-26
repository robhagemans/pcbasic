10 ' test KEY n, "aa" giving no error even if n is outside the definable key range 
20 OPEN "OUTPUT.TXT" for output as 1
30 ON ERROR GOTO 100
40 KEY 255, "1" ' ifc
50 KEY 255, "12" ' not an error
60 KEY 255, "123" ' ifc
70 PRINT#1, "end"
80 END
100 PRINT#1, ERR, ERL
110 RESUME NEXT

