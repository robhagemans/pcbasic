1 REM test if we're not trucating the last record
10 OPEN "RAND.DAT" FOR RANDOM AS 1: FIELD#1, 128 as D$
20 A=LOF(1):B=INT(A/128)+1
30 GET#1, B
40 OPEN "LENGTH.TXT" FOR OUTPUT AS 2
50 PRINT#2, LEN(D$)
60 CLOSE
