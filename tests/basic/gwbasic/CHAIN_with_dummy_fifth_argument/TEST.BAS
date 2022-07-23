1 'test for CHAIN syntax with four commas and ignored last argument
10 OPEN "output.txt" FOR OUTPUT AS 1
20 CHAIN "chain",,ALL,DELETE 10,PRINT
