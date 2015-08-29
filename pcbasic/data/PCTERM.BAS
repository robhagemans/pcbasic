1 '  PC-BASIC - PCTERM.BAS
2 '  Simple terminal emulator for the TERM statement
3 '  (c) 2015 Rob Hagemans
4 '  This file is released under the GNU GPL version 3
5 '
100 GOSUB 23000 ' Reset
110 GOSUB 30000 ' Read default settings
200 CAPTION$ = "(TERM) - Terminal Emulator"
210 XON$ = CHR$(17): XOFF$ = CHR$(19)
220 PAUSE% = 0
230 STATE% = 0
1000 ' Event loops
1020 WHILE -1
1030   CLS
1040   GOSUB 21000 ' draw key line
1050   IF STATE% THEN 3000
2000   ' Menu loop
2010   GOSUB 19000 ' close connection
2020   ON ERROR GOTO 0
2030   ON KEY(1) GOSUB 10000: KEY(1) ON ' toggle menu/comm state
2040   ON KEY(2) GOSUB 7000: KEY(2) ON ' exit
2050   KEY(3) OFF: KEY(4) OFF
2060   LOCATE 1,1,,0,7
2070   WHILE -1
2072     GOSUB 22000 ' Set width
2075     GOSUB 20000 ' draw menu screen
2080     GOSUB 24000 ' input
2090     X% = INSTR(1, CHOICE$, ",")
2100     IF X%<2 THEN 2900
2110     I% = VAL(CHOICE$)
2120     IF (I%<1) OR (I%>NSETTINGS%) THEN 2900
2130     VL$[I%] = RIGHT$(CHOICE$, LEN(CHOICE$)-X%)
2140     ECHO% = LEFT$(VL$[4],1) = "Y" OR LEFT$(VL$[4],1) = "y"
2900   WEND
3000   ' Terminal loop
3010   ON ERROR GOTO 13000
3020   OPEN "COM1:"+VL$[1]+","+VL$[3]+","+VL$[2]+",,CS,DS" AS 1
3030   ON ERROR GOTO 13100
3040   ON COM(1) GOSUB 11000: COM(1) ON ' regulate flow
3050   ON KEY(3) GOSUB 15000: KEY(3) ON ' NUL
3060   ON KEY(4) GOSUB 16000: KEY(4) ON ' Break
3070   LOCATE 1,1,,6,7
3080   WHILE -1
3090      IF EOF(1) THEN A$=INKEY$: GOTO 3090 ' EOF, wait for user interrupt
3100      GOSUB 12000 ' check flow
3110      C$ = INPUT$(1, #1)
3120      IF C$ <> CHR$(10) THEN PRINT C$;
3130      A$ = INKEY$: IF A$ = "" THEN 3130 ELSE IF LEFT$(A$,1) = CHR$(0) THEN 3130
3140      IF ECHO% THEN PRINT A$;
3150      PRINT#1, A$;
3160   WEND
4000 WEND
7000 ' Exit
7010 GOSUB 23000 ' Reset
7040 KEY ON
7050 END
10000 ' Toggle state
10010   STATE% = NOT STATE%
10020   RETURN 1000
11000 ' Stop flow
11010   IF LOC(1) > 224 AND NOT PAUSE% THEN PRINT #1,XOFF$;: PAUSE% = -1
11020   RETURN
12000 ' Start flow
12010   IF LOC(1) < 16 AND PAUSE% THEN PRINT #1,XON$;: PAUSE%=0
12020   RETURN
13000 ' Open Com errors
13010   LOCATE 23,1
13020   PRINT "File open error"
13030   STATE% = 0
13040   RESUME 1000 ' back to menu
13100 ' Errors during communication
13110   RESUME
15000 ' Send NUL
15010   PRINT#1, CHR$(0);
15020   RETURN
16000 ' Send BREAK
16010   LCR% = &H3FB ' Serial Line Control Register for COM1:
16020   LCR.STATE%=INP(LCR%)
16030   ' raise break signal
16040   OUT LCR%, LCR.STATE% OR &H40
16050   ' wait for a bit, then lower again
16050   FOR SLEEP% = 1 TO 100: NEXT SLEEP%
16060   OUT LCR,SD%
16100   RETURN
19000 ' Close connections
19010   CLOSE
19020   PAUSE% = 0
19100   RETURN
20000 ' Draw menu screen
20010   CLS
20020   LOCATE 1,1,1: ROW% = 5
20030   PRINT CAPTION$: PRINT
20040   FOR I% = 1 TO NSETTINGS%
20050     LOCATE ROW%, 1: PRINT I%; NM$[I%]
20060     LOCATE ROW%, 23: PRINT "["+VL$[I%]+"] "+RANGE$[I%]
20070     ROW% = ROW% + 1: IF ROW% = 8 THEN ROW% = 9
20080   NEXT I%
20090   GOSUB 21000
20100   RETURN
21000 ' Draw key line
21010   IF STATE% THEN KEY1$="Menu" ELSE KEY1$="Conv"
21020   LOCATE 25,1: PRINT "f1=" + KEY1$ + " f2=Exit f3=Nul f4=Break";
21030   RETURN
22000 ' Set width
22010   ON ERROR GOTO 22100
22020   WIDTH VAL(VL$[5])
22030   ON ERROR GOTO 0
22040   RETURN
22100 ' Set width - error handler
22110   VL$[5] = "40"
22120   RESUME
23000 ' Reset
23010   KEY(1) OFF: KEY(2) OFF: KEY(3) OFF: KEY(4) OFF: COM(1) OFF
23020   ON ERROR GOTO 0
23030   GOSUB 19000 ' Close connections
23040   SCREEN 0,0,0,0: CLS: KEY OFF
23050   RETURN
24000 ' Interruptible input
24020   CHOICE$ = ""
24030   WHILE -1
24040     C$ = INKEY$
24050     IF C$ = CHR$(13) THEN RETURN
24060     IF C$ = CHR$(27) THEN LOCATE 18,21: PRINT SPACE$(LEN(CHOICE$));: CHOICE$=""
24070     IF C$ >= " " THEN CHOICE$ = CHOICE$ + C$
24080     LOCATE 18,1: PRINT "Change <line,data>? "; CHOICE$;
24100   WEND
30000 ' Settings
30010   DATA "Line bit rate", "300", "(300..4800)"
30020   DATA "Data bits", "7", "(7 or 8)"
30030   DATA "Parity type", "E", "(E,O,or N)"
30040   DATA "Host echoing", "Y", "(Y or N)"
30050   DATA "Screen width", "80", "(40 or 80)"
30060   NSETTINGS% = 5
30070   FOR LIN% = 1 TO NSETTINGS%
30080     READ NM$[LIN%], VL$[LIN%], RANGE$[LIN%]
30090   NEXT
30100   RETURN
