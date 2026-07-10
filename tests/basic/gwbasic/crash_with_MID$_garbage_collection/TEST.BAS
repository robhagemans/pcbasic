100 REM NILAKANTHA FORMULA...  v. gw20250629.
110 ' SAVE "PI-NILA.BAS", A
120 ' PI=3+4/(2*3*4)-4/(4*5*6)+4/(6*7*8)-4/(8*9*10)+4/(10*11*12)-4/(12*13*14)+
130 CLS: DEFDBL A-Z
140 P = ATN(1) * 4: X = 3: T = 4 * 20000
150 FOR I%= 1 TO 577
160   N = N + 4
170   X = X + (4 / ((N - 2) * (N - 1) * N))
180   X = X - (4 / (N * (N + 1) * (N + 2)))
190   X$ = MID$(STR$(X), 2, LEN(STR$(X))-2)
200   P$ = MID$(STR$(P), 2, LEN(STR$(P))-2)
210   PRINT (N / 4); P$, X$
220   IF X$ = P$ OR N = T THEN GOTO 240
230 NEXT
240 END
