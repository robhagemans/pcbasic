10 REM PC-BASIC test 
20 REM PLAY syntax
35 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
40 ON ERROR GOTO 1000
50 PLAY
60 PLAY 10
70 PLAY "1"
75 PLAY "1", "2",
80 PLAY "1", "2"
90 PLAY "1", "2", "3"
95 PLAY "1", "2", "3",
100 PLAY "1", "2", "3", "4"
105 PLAY "1", "2", "3", "4",
107 X$="mb c": PLAY X$
110 PLAY "MFMNMLMST255"
120 PLAY "A8A16"
130 PLAY "O1ABCDEFG"
132 PLAY "A#"
134 PLAY "A+"
136 PLAY "A-"
138 PLAY "A."
140 PLAY "A>A<A"
145 PLAY "N84"
150 PLAY "L64B"
160 PLAY "L128A"
170 PLAY "P64"
250 PLAY "XX$;"
260 PLAY "XA;"
265 PLAY "X" ' no string follows, IFC
270 PLAY "X"+VARPTR$(X$)
271 ' dereference array pointer
272 Y$(1)="mb c": YPTR$ = VARPTR$(Y$(1))
273 PLAY "X" + YPTR$
274 ERASE Y$
275 PLAY "X" + YPTR$ ' detached pointer
277 PLAY "X" + VARPTR$(Z$(1)) ' undefined array
278 PLAY "X" + VARPTR$(UNDEF$) ' undefined scalar
279 PLAY "X" + CHR$(3) + CHR$(4) ' ptrstr too short
280 A=1: B(0) = 1
290 PLAY "N=A;"
300 PLAY "N=B(0);"
310 PLAY "N="+VARPTR$(A)
320 PLAY "A64."
330 PLAY "A.64"
340 PLAY "A+64."
350 PLAY "A+.64"
360 PLAY "A64+."
370 PLAY "N1."
375 PLAY "N=" ' no number follows, IFC
377 PLAY "N" ' no number follows, IFC
380 PLAY "P1."
390 PLAY "P0"
400 PLAY "P0."
999 END
1000 PRINT#1, ERR, ERL
1010 RESUME NEXT
