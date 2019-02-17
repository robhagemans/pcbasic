10 REM PC-BASIC test 
20 REM test MID$ with overlap
25 OPEN "OUTPUT.TXT" FOR OUTPUT AS 1
30 A$="12345678" 
40 MID$(A$,4)=A$ 
50 PRINT#1, "#"; A$ ;"#"
60 A$="12345678" 
70 MID$(A$,3,3)=A$ 
80 PRINT#1, "#"; A$ ;"#"
90 CLOSE

