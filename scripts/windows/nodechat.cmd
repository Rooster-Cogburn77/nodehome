@echo off
setlocal

set "NODECHAT_ENV_FILE=%USERPROFILE%\.nodehome\nodechat.env"

if exist "%NODECHAT_ENV_FILE%" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%NODECHAT_ENV_FILE%") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)

if "%NODECHAT_BASE_URL%"=="" set "NODECHAT_BASE_URL=http://192.168.1.198:8000/v1"
if "%NODECHAT_HISTORY_URL%"=="" set "NODECHAT_HISTORY_URL=http://127.0.0.1:8765"
if "%NODECHAT_WORKSPACE%"=="" set "NODECHAT_WORKSPACE=%~dp0..\.."

if "%NODECHAT_HISTORY_TOKEN%"=="" (
  echo warning: NODECHAT_HISTORY_TOKEN is not set. /history will fail if the AI History API requires auth.
)

py -3 "%~dp0..\nodechat.py" --base-url "%NODECHAT_BASE_URL%" --history-url "%NODECHAT_HISTORY_URL%" --workspace "%NODECHAT_WORKSPACE%" %*
