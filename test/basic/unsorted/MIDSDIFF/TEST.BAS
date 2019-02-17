10 REM PC-BASIC test 
20 REM test MID$ with overlap
25 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
30 A$="12345678": B$="abcdefgh"
40 MID$(A$,4)=B$ 
50 PRINT#1, "#"; A$ ;"# #"; B$; "#"
60 A$="12345678" 
70 MID$(A$,3,3)=B$ 
80 PRINT#1, "#"; A$ ;"# #"; B$; "#"
90 CLOSE

