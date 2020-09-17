10 REM PC-BASIC test 
20 REM
30 dim a%[100]
40 screen 1
50 line (5,5)-(100,100),1,bf
60 get(0,0)-(10,10),a%
70 PUT (20,20),a%,PSET
80 PUT (22,20),a%,PRESET
90 PUT (24,20),a%,AND
100 PUT (26,20),a%,OR
110 PUT (28,20),a%,XOR
170 PUT (120,20),a%,PSET
180 PUT (122,20),a%,PRESET
190 PUT (124,20),a%,AND
200 PUT (126,20),a%,OR
210 PUT (128,20),a%,XOR
120 def seg=&hb800:bsave "output.bsv", 0, 8000

