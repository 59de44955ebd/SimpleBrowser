@echo off

set DOWNLOAD_DIR=%USERPROFILE%\Downloads

cd /d "%DOWNLOAD_DIR%"

REM use a timestamp as filename
set datetimestr=%date:~6,4%-%date:~3,2%-%date:~0,2%_%time:~0,2%-%time:~3,2%-%time:~6,2%

set u=%~1

REM list available formats
yt-dlp -F "%u%"
echo.
set /P fmt="Please select a format code (combine 2 codes with +): "
echo.

REM start download
yt-dlp -f %fmt% --no-mtime -o "%datetimestr%.%%(ext)s" "%u%"

echo.
echo Video saved to folder %DOWNLOAD_DIR%
explorer "%DOWNLOAD_DIR%"

echo.
pause
