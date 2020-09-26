10 ' test INSTR with string not found
20 open "output.txt" for output as 1
30 print#1, INSTR("abcd","e")
40 close:end

