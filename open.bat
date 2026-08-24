@echo off
REM Opens the report over a real http:// origin so that stars and discards
REM persist reliably in every browser.  Leave this window open while browsing.
cd /d "%~dp0"
start "" http://127.0.0.1:8777/index.html
"C:\Program Files\Python313\python.exe" -m http.server 8777 --bind 127.0.0.1
