1 ' test "undefined line number"
2 CLS:KEY OFF
3 open "errors.txt" for output as 2
5 ON ERROR GOTO 2000
10 ? "hi"
15 GOSUB 10020
20 N$="output.txt": GOSUB 1000
999 END
1000 ' dump screen
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 24
1040 FOR X = 0 TO 79
1050 PRINT #1, CHR$(PEEK(2*(Y*80+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1
1090 RETURN
2000 PRINT#2, ERR, ERL
2010 RESUME NEXT
10000 ' undefined line number follows
10010
10020 ' what follows is ignored
10030 ? "bye"
10040 return

