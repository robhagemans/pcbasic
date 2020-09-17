1 ' flood fill region with two holes (and yet don't loop forever)
5 SCREEN 1: CLS
10 LINE (10,10) - (40,40), 4, b
20 line (20,20)-(23,23),4,b
30 line (27,20)-(30,23),4,b
40 PAINT (35, 21),"ABCA",4
50 PAINT (35, 21),"ABCA",4, "A"
110 LINE (110,10) - (140,40), 4, b
120 line (120,20)-(123,23),4,b
130 line (127,20)-(130,23),4,b
140 PAINT (135, 21),1,4
2000 R.X0%=5: R.X1%=145: R.Y0%=5: R.Y1%=45: R.BPP%=2: GOSUB 10000
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

