5 OPEN "output.txt" for output as 1
6 open "lpt1:" for output as 2
100 print#1, "width#2 23"
120 width#2, 23:gosub 1000: gosub 2000
200 print#1, "width lprint 21"
220 width lprint 21:gosub 1000: gosub 2000
300 print#1, "width lpt1 43"
320 width "lpt1:", 43:gosub 1000: gosub 2000
400 width#2, 255: gosub 1000: gosub 2000
500 width lprint 255: gosub 1000: gosub 2000
600 width "lpt1:", 255: gosub 1000: gosub 2000
999 END
1000 print#1, "print#2":for c = 0 to 255
1020 PRINT#2, chr$(c);:PRINT#1, c, LPOS(0)
1030 next:print#2,
1040 return
2000 print#1, "lprint":for c = 0 to 255
2020 LPRINT chr$(c);:PRINT#1, c, LPOS(0)
2030 next:lprint
2040 return

