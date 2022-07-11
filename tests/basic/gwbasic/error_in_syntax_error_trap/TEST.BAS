1 ' test interrupting a syntax error trap by an illegal function call
5 WIDTH 40: CLS: KEY OFF
10 ON ERROR GOTO 100
20 THIS IS A SYNTAX ERROR
30 END
100 PRINT "error trap"
105 COLOR 1000 ' illegal function call
110 RESUME NEXT
1000 N$="output.txt" ' RUN 1000 to dump screen
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 10
1040 FOR X = 0 TO 39
1050 PRINT #1, CHR$(PEEK(2*(Y*40+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1

