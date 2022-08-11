10 ' test funny characters in file names
15 open "errors.txt" for output as 2 
20 on error goto 1000
30 open chr$(0) for output as 1
40 close
90 end
1000 print#2, err, erl
1010 resume next

