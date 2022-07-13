1 ' read from the redefinable font memory
2 ' note that the actual output depends on the 8-pixel font loaded
10 def seg=&hc000
20 a = peek(&h500)
100 open "output.txt" for output as 1
110 print#1, a
120 close

