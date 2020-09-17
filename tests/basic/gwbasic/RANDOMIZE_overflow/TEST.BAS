10 ' test causing overflow in RANDOMIZE prompt
20 open "output.txt" for output as 1
30 on error goto 100
40 RANDOMIZE
50 print#1, RND
60 close: end
100 print#1, err, erl
110 resume next

