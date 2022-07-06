1 ' test pressing ESC on an input row, on the logical line of the prompt
10 WIDTH 40: CLS: KEY OFF
20 INPUT "", A$
30 OPEN "value.txt" for output as 2
40 WRITE#2, A$
50 CLOSE
90 N$="output.txt": GOSUB 1000
999 END
1000 ' dump screen
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 6
1040 FOR X = 0 TO 39
1050 PRINT #1, CHR$(PEEK(2*(Y*40+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1
