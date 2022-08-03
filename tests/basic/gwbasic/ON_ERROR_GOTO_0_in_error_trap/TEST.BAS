10 ' test ON ERROR GOTO 0 inside error trap
15 width 40: key off
20 on error goto 100
30 syntax error
40 end
100 print 1
110 on error goto 0
1000 N$="output.txt" ' RUN 1000 to dump screen
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 10
1040 FOR X = 0 TO 20
1050 PRINT #1, CHR$(PEEK(2*(Y*40+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1

