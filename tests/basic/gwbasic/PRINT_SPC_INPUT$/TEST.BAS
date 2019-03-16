1 ' test waiting for input while in PRINT statement
5 open "output.txt" for output as 1
10 PRINT#1, 1 SPC(VAL(INPUT$(1))) 9
20 close

