1000 '  PC-BASIC - PCTERM.BAS
1010 '  Simple terminal emulator for the TERM statement
1020 '  Copyright (c) 2015, 2016 Rob Hagemans
1030 '  This file is released under the Expat MIT licence [https://opensource.org/licenses/MIT]
1040 '
1050 GOSUB 2090 ' Reset
1060 GOSUB 2240 ' Read default settings
1070 CAPTION$ = "(TERM) - Terminal Emulator"
1080 XON$ = CHR$(17): XOFF$ = CHR$(19)
1090 PAUSE% = 0
1100 STATE% = 0
1110 ' Event loops
1120 WHILE -1
1130   CLS
1140   GOSUB 1970 ' draw key line
1150   IF STATE% THEN 1330
1160   ' Menu loop
1170   GOSUB 1820 ' close connection
1180   ON ERROR GOTO 0
1190   ON KEY(1) GOSUB 1550: KEY(1) ON ' toggle menu/comm state
1200   ON KEY(2) GOSUB 1510: KEY(2) ON ' exit
1210   KEY(3) OFF: KEY(4) OFF
1220   LOCATE 1,1,,0,7
1230   WHILE -1
1240     GOSUB 2010 ' Set width
1250     GOSUB 1860 ' draw menu screen
1260     GOSUB 2150 ' input
1270     X% = INSTR(1, CHOICE$, ",")
1280     IF X%<2 THEN 1320
1290     I% = VAL(CHOICE$)
1300     IF (I%<1) OR (I%>NSETTINGS%) THEN 1320
1310     VL$[I%] = RIGHT$(CHOICE$, LEN(CHOICE$)-X%)
1320   WEND
1330   ' Terminal loop
1340   ON ERROR GOTO 1640
1350   OPEN "COM1:"+VL$[1]+","+VL$[3]+","+VL$[2]+",,CS,DS" AS 1
1360   ON ERROR GOTO 1690
1370   ON COM(1) GOSUB 1580: COM(1) ON ' regulate flow
1380   ON KEY(3) GOSUB 1710: KEY(3) ON ' NUL
1390   ON KEY(4) GOSUB 1740: KEY(4) ON ' Break
1400   LOCATE 1,1,,6,7
1410   WHILE -1
1420      IF EOF(1) THEN 1460
1430      GOSUB 1610 ' check flow
1440      C$ = INPUT$(1, #1)
1450      IF C$ <> CHR$(10) THEN PRINT C$;
1460      A$ = INKEY$: IF A$ = "" THEN 1410 ELSE IF LEFT$(A$,1) = CHR$(0) THEN 1460
1470      IF LEFT$(VL$[4],1) = "Y" OR LEFT$(VL$[4],1) = "y" THEN PRINT A$;
1480      PRINT#1, A$;
1490   WEND
1500 WEND
1510 ' Exit
1520 GOSUB 2090 ' Reset
1530 KEY ON
1540 END
1550 ' Toggle state
1560   STATE% = NOT STATE%
1570 RETURN 1110
1580 ' Stop flow
1590   IF LOC(1) > 224 AND NOT PAUSE% THEN PRINT #1,XOFF$;: PAUSE% = -1
1600 RETURN
1610 ' Start flow
1620   IF LOC(1) < 16 AND PAUSE% THEN PRINT #1,XON$;: PAUSE%=0
1630 RETURN
1640 ' Open Com errors
1650   LOCATE 23,1
1660   PRINT "File open error"
1670   STATE% = 0
1680 RESUME 1110 ' back to menu
1690 ' Errors during communication
1700 RESUME
1710 ' Send NUL
1720   PRINT#1, CHR$(0);
1730 RETURN
1740 ' Send BREAK
1750   LCR% = &H3FB ' Serial Line Control Register for COM1:
1760   LCR.STATE%=INP(LCR%)
1770   ' raise break signal
1780   OUT LCR%, LCR.STATE% OR &H40
1790   FOR SLEEP% = 1 TO 100: NEXT SLEEP%
1800   OUT LCR,SD%
1810 RETURN
1820 ' Close connections
1830   CLOSE
1840   PAUSE% = 0
1850 RETURN
1860 ' Draw menu screen
1870   CLS
1880   LOCATE 1,1,1: ROW% = 5
1890   PRINT CAPTION$: PRINT
1900   FOR I% = 1 TO NSETTINGS%
1910     LOCATE ROW%, 1: PRINT I%; NM$[I%]
1920     LOCATE ROW%, 23: PRINT "["+VL$[I%]+"] "+RANGE$[I%]
1930     ROW% = ROW% + 1: IF ROW% = 8 THEN ROW% = 9
1940   NEXT I%
1950   GOSUB 1970
1960 RETURN
1970 ' Draw key line
1980   IF STATE% THEN KEY1$="Menu" ELSE KEY1$="Conv"
1990   LOCATE 25,1: PRINT "f1=" + KEY1$ + " f2=Exit f3=Nul f4=Break";
2000 RETURN
2010 ' Set width
2020   ON ERROR GOTO 2060
2030   WIDTH VAL(VL$[5])
2040   ON ERROR GOTO 0
2050 RETURN
2060 ' Set width - error handler
2070   VL$[5] = "40"
2080 RESUME
2090 ' Reset
2100   KEY(1) OFF: KEY(2) OFF: KEY(3) OFF: KEY(4) OFF: COM(1) OFF
2110   ON ERROR GOTO 0
2120   GOSUB 1820 ' Close connections
2130   SCREEN 0,0,0,0: CLS: KEY OFF
2140 RETURN
2150 ' Interruptible input
2160   CHOICE$ = ""
2170   WHILE -1
2180     C$ = INKEY$
2190     IF C$ = CHR$(13) THEN RETURN
2200     IF C$ = CHR$(27) THEN LOCATE 18,21: PRINT SPACE$(LEN(CHOICE$));: CHOICE$=""
2210     IF C$ >= " " THEN CHOICE$ = CHOICE$ + C$
2220     LOCATE 18,1: PRINT "Change <line,data>? "; CHOICE$;
2230   WEND
2240 ' Settings
2250   DATA "Line bit rate", "300", "(300..4800)"
2260   DATA "Data bits", "7", "(7 or 8)"
2270   DATA "Parity type", "E", "(E,O,or N)"
2280   DATA "Host echoing", "Y", "(Y or N)"
2290   DATA "Screen width", "80", "(40 or 80)"
2300   NSETTINGS% = 5
2310   FOR LIN% = 1 TO NSETTINGS%
2320     READ NM$[LIN%], VL$[LIN%], RANGE$[LIN%]
2330   NEXT
2340 RETURN
