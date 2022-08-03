1 ' test CONT after STOP in error trap with Syntax Error
2 ' dump screen to show Break, EDIT line
10 WIDTH 40: CLS
15 ON ERROR GOTO 100
20 PRINT 1
30 SYNTAX ERROR
40 PRINT 2
99  END
100 ' error trap
110 STOP
120 RESUME NEXT
999 END
1000 ' dump screen
1005 N$="output.txt"
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 24
1040 FOR X = 0 TO 39
1050 PRINT #1, CHR$(PEEK(2*(Y*40+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1
