10 ' test RND with negative argument 
20 open "output.txt" for output as 1
30 print#1, RND(-1)
40 print#1, RND(-2e34)
50 print#1, RND
60 close

