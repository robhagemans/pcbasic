0 ' PAINT tests with tile and background patterns
1 SCREEN 1: CLS
2 OPEN"ERRORS.TXT" FOR OUTPUT AS 2:ON ERROR GOTO 20000
4 'tile over coloured background - doesn't fill out
5 LINE (10,10)-(20,20),1,BF
10 LINE (10,10)-(20,20), 3,B
20 PAINT (15,15),CHR$(&H55)+CHR$(&HAA),3
100 'specify bg pattern to allow pattern fill over matching colour
105 LINE (30,10)-(40,20),1,BF
110 LINE (30,10)-(40,20), 3,B
120 PAINT (35,15),CHR$(&H55)+CHR$(&HAA),3,CHR$(&H55)
200 'tile over same pattern - no error
205 LINE (50,30)-(60,40),1,BF
210 LINE (50,30)-(60,40), 3,B
220 PAINT (55,35),CHR$(&H55)+CHR$(&HAA),3,CHR$(&H55)
225 PAINT (55,35),CHR$(&H55)+CHR$(&HAA),3,CHR$(&H55)+CHR$(&HAA)
300 'tile over different pattern
305 LINE (50,10)-(60,20),1,BF
310 LINE (50,10)-(60,20), 3,B
320 PAINT (55,15),CHR$(&H55)+CHR$(&HAA)+CHR$(&HFF),3,CHR$(&H55)
325 PAINT (55,15),CHR$(&H55)+CHR$(&HAA)+CHR$(&H0),3,CHR$(&H55)+CHR$(&HAA)+CHR$(&HFF)
400 'tile over different pattern - only one row of dots
405 LINE (70,10)-(80,20),1,BF
410 LINE (70,10)-(80,20), 3,B
420 PAINT (75,15),CHR$(&H55)+CHR$(&HAA)+CHR$(&HFF)+CHR$(0),3,CHR$(&H55)
425 PAINT (75,15),CHR$(&H55)+CHR$(&HAA)+CHR$(&H0)+CHR$(&H11),3,CHR$(&H55)+CHR$(&HAA)+CHR$(&HFF)+CHR$(0)
500 'fill over tiled background
505 LINE (90,10)-(100,20),1,BF
510 LINE (90,10)-(100,20), 3,B
520 PAINT (95,15),"QWER",3
525 PAINT (95,15),"ABCD",3, "QWER"
600 'background string matches pattern string
605 LINE (90,30)-(100,40),1,BF
610 LINE (90,30)-(100,40), 3,B
620 PAINT (95,35),"ADFR",3
625 PAINT (95,35),"QWER",3, "QWER"
700 'background chars ignored beyond first? black bars don't all get filled
705 LINE (70,30)-( 80,40),1,BF
710 LINE (70,30)-( 80,40), 3,B
720 PAINT (75,35),CHR$(&H55)+CHR$(&HAA),3,CHR$(&H55)
725 PAINT (75,35),CHR$(&H55)+CHR$(&HAA)+CHR$(0)+CHR$(0),3,CHR$(&H55)+CHR$(&HAA)
1000 'background chars ignored beyond first? no difference from just chr$(&h55)
1005 LINE (10,30)-(20,40),1,BF
1010 LINE (10,30)-(20,40), 3,B
1020 PAINT (15,35),CHR$(&H55)+CHR$(&HAA),3, CHR$(&H55)+"YOLO"
1100 'illegal fn call
1105 LINE (30,30)-(40,40),1,BF
1110 LINE (30,30)-(40,40), 3,B
1120 PAINT (35,35),CHR$(&H55)+CHR$(&H55)+CHR$(&H55),3, CHR$(&H55)+"YOLO"
2000 R.X0%=5: R.X1%=105: R.Y0%=5: R.Y1%=45: R.BPP%=2: GOSUB 10000
9999 CLOSE:END
10000 'save screen region (R.X0%, R.Y0%)-(R.X1%, R.Y1%) with R.BPP% bits per pixel
10140 LINE (R.X0%, R.Y0%)-(R.X1%, R.Y1%),1,B
10145 R.SIZE% = (R.X1%-R.X0%+16\R.BPP%) * (R.Y1%-R.Y0%+1) + 2
10147 R.SIZE% = R.SIZE%*R.BPP%\16
10150 DIM R.SPRITE%(R.SIZE%)
10160 GET (R.X0%, R.Y0%)-(R.X1%, R.Y1%), R.SPRITE%
10165 OPEN "output.txt" FOR OUTPUT AS 1
10167 PRINT#1, R.SPRITE%(0), R.SPRITE%(1)
10170 FOR I=0 TO R.SIZE%
10190   PRINT#1, HEX$(R.SPRITE%(I)); " ";
10200   IF I MOD 16=15 THEN PRINT#1,
10220 NEXT
10275 CLOSE 1
10300 RETURN
20000 PRINT#2, ERR, ERL
20010 RESUME NEXT


