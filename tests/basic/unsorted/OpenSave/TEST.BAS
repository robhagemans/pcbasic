10 REM PC-BASIC test 
20 REM SAVE to an OPEN file
30 open "errors.txt" for output as 3
40 on error goto 1000
50 open "prog.bas" for output as 1
60 print#1, "test"
70 save "prog"
80 close:end
1000 print#3, err, erl
1010 resume next
