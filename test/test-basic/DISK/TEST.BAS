10 REM PC-BASIC test 
20 REM disk operations
30 mkdir "test0"
40 mkdir "test1"
50 chdir "test0"
60 open "test.txt" for output as 1
70 print#1, "test"
80 close
90 name "test.txt" as "test0.txt"
100 chdir "..\test1"
160 open "test.txt" for output as 1
170 print#1, "test"
180 close
190 kill "test.txt"
200 chdir ".."
210 rmdir "test1"
260 open "test.txt" for output as 1
270 print#1, "test"
280 close
290 end
