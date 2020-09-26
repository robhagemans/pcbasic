10 REM PC-BASIC test 
20 REM WIDTH syntax
30 open "output.txt" for output as 1
40 on error goto 10000
50 width 40
60 width 80
70 width 39.5
80 width "scrn:", 79.5
85 width "scrn:" 80
90 width 39+1
100 width (79+1)
110 width "40"
115 print#1, "lprint"
120 width lprint 40
125 width lprint 256
130 width lprint 32768
140 width lprint 0
150 width lprint -1
220 width lprint 40
225 width 256
230 width 32768
240 width 0
250 width -1
300 print #1, "()"
320 width (256)
330 width (32768)
340 width (0)
350 width (-1)
400 print#1, "scrn:"
420 width "scrn:", 40
425 width "scrn:", 256
430 width "scrn:", 32768
440 width "scrn:", 0
450 width "scrn:", -1
460 width "scrn:", 40
520 width#1, 200
525 width#1, 256
530 width#1, 32768
540 width#1, 0
550 width#1, -1
600 width "scrn:", 1,2
610 width 40, 25
620 width 80, 25
630 width 40, 20
640 width 80, 50
650 width 40, 2, 3
660 width
9999 end
10000 print#1, "error", err, erl
10010 resume next
