10 CLS:LOCATE 4,1:OPEN "output.txt" FOR OUTPUT AS 1
12 FILES "output.txt"
15 locate csrlin-3,1
20 BF$="":FOR I=1 TO 12:BF$=BF$+CHR$(SCREEN(CSRLIN, I)):NEXT
25 locate csrlin+3,1
30 print#1, "[";bf$;"]":close


