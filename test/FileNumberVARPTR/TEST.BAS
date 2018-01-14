10 REM PC-BASIC test 
20 REM VARPTR to file buffer
30 open "output.txt" for output as 1
40 on error goto 1000
50 for i = 0 to 5
60   print#1, varptr(#i)
70 next
80 end
1000 print#1, err, erl
1010 resume next

