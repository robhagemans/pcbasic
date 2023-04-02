1 ' test DRAW with turn angle (TA)
2 ' note how the aspect ratio is preserved
10 CLS:KEY OFF:SCREEN 1
20 FOR I = 0 TO 360 STEP 13
30 DRAW "ta=i;u90d90"
40 NEXT
45 ' true circle is not identical
50 'CIRCLE STEP (0,0),90
60 FOR I = 0 TO 360 STEP 13
70 DRAW "c2;ta=i;l90r90"
80 NEXT
90 DEF SEG=&HB800:BSAVE "drawing.bsv", 0, 32767
