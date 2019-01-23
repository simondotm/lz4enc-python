..\smallz4.py %1
..\bin\lz4.exe -9 -f %1 %1.a.lz4
..\bin\smallz4-v1.3.exe -9 -f %1 %1.b.lz4
..\bin\lz4.exe -d -f %1.lz4 z.%1

fc /b /a %1 z.%1
