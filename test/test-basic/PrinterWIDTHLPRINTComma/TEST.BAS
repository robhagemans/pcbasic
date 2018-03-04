5 OPEN "output.txt" for output as 1
6 open "lpt1:" for output as 2
210 for w%=1 to 255 step 7
220 width lprint w%:gosub 1000: gosub 2000
230 next w%
999 END
1000 for c = 0 to 255
1020 PRINT#2,, chr$(c);:PRINT#1, w%, "#2",  c, LPOS(0)
1030 next:print#2,
1040 return
2000 for c = 0 to 255
2020 LPRINT, chr$(c);:PRINT#1, w%, "LP", c, LPOS(0)
2030 next:lprint
2040 return

