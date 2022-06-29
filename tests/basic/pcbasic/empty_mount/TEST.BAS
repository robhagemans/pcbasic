1 ' test pcbasic with empty --mount
2 'writing to z: should fail
10 open "z:test.txt" for output as 1
20 print#1, "this should not be written" 
30 close 1
