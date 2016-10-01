10 REM PC-BASIC test 
20 REM calculated jumps
30 open "output.txt" for output as 1
40 on error goto 1000
50 print#1, 50
60 a = 0: gosub 500
61 a = 1: gosub 500
62 a = 2: gosub 500
63 a = 3: gosub 500
64 a = 4: gosub 500
65 a = 5: gosub 500
66 a = 6: gosub 500
67 a = 0.4: gosub 500
68 a=0.5: gosub 500
69 a = -1: gosub 500
70 a = 255: gosub 500
71 a = 256: gosub 500
72 a = 32767: gosub 500
73 a = 65535: gosub 500
160 a = 0: gosub 600
161 a = 1: gosub 600
162 a = 2: gosub 600
163 a = 3: gosub 600
164 a = 4: gosub 600
165 a = 5: gosub 600
166 a = 6: gosub 600
167 a = 0.4: gosub 600
168 a=0.5: gosub 600
169 a = -1: gosub 600
170 a = 255: gosub 600
171 a = 256: gosub 600
172 a = 32767: gosub 600
173 a = 65535: gosub 600
200 a = -1: gosub 700
210 a = 0: gosub 700
220 a = 1: gosub 700
230 end
500 on a goto 520, 530, 540, print, 550
510 print#1, 510: return
520 print#1, 520: return
530 print#1, 530: return
560 print#1, 560: return
600 on a gosub 620, 630, 640, print, 650
610 print#1, 610: return
620 print#1, 620: return
630 print#1, 630: return
660 print#1, 660: return
700 on a
710 print#1, 710: return
1000 print#1, err, erl
1010 resume next


