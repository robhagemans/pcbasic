1 ' test printing right-arrow control in the bottom right cell
10 WIDTH 40: CLS
20 PRINT "top"
30 LOCATE 24,40
40 PRINT chr$(&H1C); ' control code: move right
50 locate 1,10
60 print "middle"
90 N$="output.txt": GOSUB 1000
999 END
1000 ' dump screen
1010 DEF SEG=&HB800
1020 OPEN N$ FOR OUTPUT AS 1
1030 FOR Y = 0 TO 24
1040 FOR X = 0 TO 39
1050 PRINT #1, CHR$(PEEK(2*(Y*40+X)));
1060 NEXT
1065 PRINT #1, ""
1070 NEXT
1080 CLOSE 1
