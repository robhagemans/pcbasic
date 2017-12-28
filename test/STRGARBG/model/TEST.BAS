10 REM PC-BASIC test 
20 REM garbage collection
30 OPEN "ERRORS.TXT" FOR OUTPUT AS 1
35 OPEN "OUTPUT.TXT" FOR OUTPUT AS 2
40 ON ERROR GOTO 1000
50 REM create some strings in code and string space
60 A$(0)="test"
70 A$(1)=A$(0)+"1"
80 A$(2)=A$(0)+"2"
90 A$(3)=A$(0)+"3"
95 A$(4)=A$(0)+"4"
99 GOSUB 500
150 REM turn them to garbage
160 A$(0)="TEST"
170 A$(1)=A$(0)+"1"
180 A$(2)=A$(0)+"2"
190 A$(3)=A$(0)+"3"
195 A$(4)=A$(0)+"4"
199 GOSUB 500
200 REM collect garbage
210 X = FRE("")
220 GOSUB 500
490 END
499 REM show strings and addresses
500 FOR I=0 TO 5
510 PRINT#2, A$(I), PEEK(VARPTR(A$(I))), PEEK(VARPTR(A$(I))+1), PEEK(VARPTR(A$(I))+2)
520 NEXT
530 RETURN
1000 PRINT#1, ERR, ERL
1010 RESUME NEXT


