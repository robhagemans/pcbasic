1 ' test RANDOM file, assigning FIELD variable to array member
10 OPEN "R",#1,"INPUT.DAT",10
20 FIELD#1,10 AS W$
30 LSET W$="A"
40 PUT#1,1
50 LSET W$="B"
60 PUT#1,2
70 CLOSE
100 REM Read the file
105 DIM X$(2)
110 OPEN "R",#1,"INPUT.DAT",10
120 FIELD#1,10 AS R$
130 GET#1,1
140 X$(1)=R$: Y$=R$
150 GET#1,2
160 X$(2)=R$: Z$=R$
170 OPEN "OUTPUT.TXT" FOR OUTPUT AS 2
200 PRINT#2, R$
210 PRINT#2, X$(1);X$(2);Y$;Z$
220 CLOSE

