10 ' read field varuables and assign them to scalar or array
20 ' the targets should copy, not reference, the field string
100 DIM X$(2)
110 OPEN "R",#1,"INPUT.DAT",10
115 OPEN "OUTPUT.TXT" FOR OUTPUT AS 2
120 FIELD#1,10 AS R$
130 GET#1,1
135 X$(1)=R$: Y$=R$
140 PRINT#2, R$
150 GET#1,2
160 X$(2)=R$: Z$=R$
200 PRINT#2, R$
210 PRINT#2, X$(1);X$(2);Y$;Z$
220 CLOSE 

