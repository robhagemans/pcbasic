1 OPEN "OUTPUT" FOR OUTPUT AS 1
5 Z$= STRING$(4,0)
10 DATA &haa, &h77, &h17, &h72
20 DATA &h41, &he8, &hd6, &h61
25 GOTO 100
30 A$="": FOR I%=1 TO 4
40 READ A%
50 A$ = A$+CHR$(A%)
60 NEXT
70 RETURN
100 GOSUB 30: L$=A$
110 GOSUB 30: R$=A$
120 S$=MKS$(CVS(L$)+CVS(R$))
125 D$=MKD$(CVD(Z$+L$)+CVD(Z$+R$))
130 FOR I%=1 TO 4
140 PRINT#1, HEX$(ASC(MID$(S$,I%)));" ";
150 NEXT
160 PRINT#1, "",
161 FOR I%=1 TO 8
162 PRINT#1, HEX$(ASC(MID$(D$,I%)));" ";
163 NEXT
164 PRINT#1, ""
170 GOTO 100
1010 DATA &haa, &h00, &h17, &h72
1020 DATA &h41, &h80, &hd6, &h61
1030 DATA &haa, &h00, &h00, &h72
1040 DATA &h41, &h80, &hd6, &h61
1050 DATA &haa, &h00, &h00, &h72
1060 DATA &h00, &h80, &hd6, &h61
1070 DATA &haa, &h00, &h00, &h72
1080 DATA &h01, &h80, &hd6, &h61
1090 DATA &haa, &h00, &h00, &h72
1100 DATA &h01, &h00, &hd6, &h61
1110 DATA &haa, &h00, &h00, &h72
1120 DATA &h01, &h40, &hd6, &h61
1130 DATA &h01, &h00, &h00, &h72
1140 DATA &h01, &h80, &hd6, &h61
1150 DATA &h01, &h00, &h00, &h72
1160 DATA &h00, &h80, &hd6, &h61
1170 DATA &h00, &h00, &h00, &h72
1180 DATA &h01, &h80, &hd6, &h61
1190 DATA &h00, &h00, &h00, &h72
1200 DATA &h00, &h80, &hd6, &h61
1290 DATA &h00, &h00, &h00, &h72
1300 DATA &h01, &h80, &hd6, &h60
1310 DATA &h00, &h00, &h00, &h72
1320 DATA &h00, &h80, &hd6, &h60
1330 DATA &h00, &h00, &h00, &h72
1340 DATA &h01, &h80, &hd6, &h5f
1350 DATA &h00, &h00, &h00, &h72
1360 DATA &h00, &h80, &hd6, &h5f
1370 DATA &h00, &h00, &h00, &h72
1380 DATA &h01, &h80, &hf0, &h5f
1390 DATA &h00, &h00, &h00, &h72
1400 DATA &h00, &h80, &hf0, &h5f

