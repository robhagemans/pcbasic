10 REM PC-BASIC test 
20 REM different files with the same name are considered the same
25 open "errors.txt" for output as 3
28 on error goto 1000
30 open "output.txt" for output as 1
40 mkdir "dir"
50 open "dir\output.txt" for output as 2
60 print#1, "one"
70 print#2, "two"
80 close 2
90 close 1
900 end
1000 print#3, err, erl
1010 resume next

