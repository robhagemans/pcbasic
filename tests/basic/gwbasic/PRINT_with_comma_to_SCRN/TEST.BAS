1 ' test PRINT with comma to SCRN:
5 OPEN "scrn:" for output as 2
6 open "pos.txt" for output as 1
210 for w%=1 to 255 
220 width#2, w%:gosub 1000
230 next w%
999 END
1000 PRINT#2,, "x";:PRINT#1, w%, "#2", pos(0):print#2,
1040 return

