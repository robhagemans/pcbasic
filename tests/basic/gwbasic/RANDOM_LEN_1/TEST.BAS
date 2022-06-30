10 ' test record length setting for RANDOM files
11 ' issue #187
20 OPEN "len_1.txt" FOR RANDOM AS #1 LEN=1:PUT #1:CLOSE 1

