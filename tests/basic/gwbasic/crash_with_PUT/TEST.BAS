5 REM Test crash on PUT
6 REM https://github.com/robhagemans/pcbasic/issues/128
10 SIZE=20
20 DIM S(SIZE*SIZE)
30 SCREEN 7 : CLS
40 LINE(100,100)-(100+SIZE,100+SIZE),4,BF
50 GET(100,100)-(100+SIZE,100+SIZE),S
60 CLS
70 REM PLAY "p1 p1"
80 PUT(100,100),S

