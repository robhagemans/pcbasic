5 ' test unsetting key macro, allowing to use F1 in INKEY$
6 open "output.txt" for output as 1
10 KEY 1, ""
20 A$=INKEY$: IF A$="z" THEN END
30 IF A$=CHR$(0)+CHR$(&H3B) THEN PRINT#1, "f1"
40 IF A$<>"" THEN PRINT#1, HEX$(ASC(A$));
45 IF LEN(A$)>1 THEN PRINT#1, HEX$(ASC(RIGHT$(A$,1)));
46 IF A$<>"" THEN PRINT#1, "#"
50 GOTO 20

