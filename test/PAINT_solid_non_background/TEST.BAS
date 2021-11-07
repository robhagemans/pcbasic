1 ' test pattern flood fill with solid rows in a non-background attribute
2 ' unlike with background atribute 0, here the pattern fill breaks off after one row
5 CLS
10 SCREEN 1
20 CIRCLE(100,100),50,2
30 PAINT(100,100),2
40 PAINT (100,100),CHR$(0)+CHR$(&HAA),2
50 PAINT (100,100),CHR$(&HAA)+CHR$(0),2
60 ATTR = POINT(100,102)
100 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
110 PRINT#1, ATTR
120 CLOSE

