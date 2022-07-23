10 ' test PRInT USING with floats in scientific notation 
20 open "output.txt" for output as 1
30 print#1, using "#,###.#######^^^^"; 1e6
35 print#1, using "#,###.####^^^^"; 1e6
40 print#1, using "#^^^^"; 1
50 print#1, using "#^^^^"; 0
60 print#1, using "####.^^^^"; 1000
70 print#1, using "#.^^^^"; 0
80 print#1, using "##,###.";1e6
1000 close:end

