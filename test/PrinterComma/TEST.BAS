5 OPEN "output.txt" for output as 1
6 open "lpt1:" for output as 2
210 for w%=1 to 255 
220 width lprint w%:gosub 1000
230 next w%
310 for w%=1 to 255 
320 width lprint w%:gosub 2000
330 next w%
999 END
1000 PRINT#2,, "x";:PRINT#1, w%, "#2", LPOS(0):print#2,
1040 return
2000 LPRINT, "x";:PRINT#1, w%, "LP", LPOS(0):lprint
2040 return

