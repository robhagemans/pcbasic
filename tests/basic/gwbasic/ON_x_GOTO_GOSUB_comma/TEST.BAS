10 REM PC-BASIC test 
20 REM calculated jumps
30 open "output.txt" for output as 1
40 on error goto 1000
50 print#1, 50
60 a = 0: gosub 500
61 a = 1: gosub 500
62 a = 2: gosub 500
69 a = -1: gosub 500
70 a = 255: gosub 500
71 a = 256: gosub 500
72 a = 32767: gosub 500
73 a = 65535: gosub 500
160 a = 0: gosub 600
161 a = 1: gosub 600
162 a = 2: gosub 600
169 a = -1: gosub 600
170 a = 255: gosub 600
171 a = 256: gosub 600
172 a = 32767: gosub 600
173 a = 65535: gosub 600
490 end
500 on a goto,
510 print#1, 510: return
600 on a gosub,
610 print#1, 610: return
1000 print#1, err, erl, a
1010 resume next


