1 ' related to bug https://github.com/robhagemans/pcbasic/issues/120
2 ' test pattern fill with one row completely empty (e.g. equal to background)
3 ' flood fill should not stop on this row
4 ' despite fix for issue #120
10 SCREEN 1:CLS
20 CIRCLE(150,150),20
30 PAINT(150,150),CHR$(&H80)+CHR$(&H0)+CHR$(&H70)
35 ' should be 1 (part of pattern) not 0 (background)
40 ATTR = POINT(148, 161)
50 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
60 PRINT#1, ATTR
70 CLOSE

