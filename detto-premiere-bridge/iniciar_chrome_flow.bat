@echo off
chcp 65001 >nul
REM ==============================================================================================
REM  CHROME DEDICADO AO GOOGLE FLOW (porta 9222) - o DETTO conecta nele por CDP.
REM  1a vez: entre na sua conta Google (a da assinatura com os creditos) NESTA janela. O login fica
REM  guardado em chrome_flow_profile\ (pasta so deste Chrome; nunca vai para o Git).
REM  Deixe esta janela ABERTA enquanto o DETTO gera clipes (pode minimizar).
REM ==============================================================================================
setlocal
set "PERFIL=%~dp0chrome_flow_profile"
set "CHROME="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "CHROME=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not defined CHROME (
  echo [ERRO] Nao achei o Google Chrome. Instale o Chrome e rode de novo.
  pause
  exit /b 1
)
REM ja esta aberto? (porta 9222 respondendo)
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 http://127.0.0.1:9222/json/version) | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo O Chrome do Flow ja esta aberto na porta 9222. Nada a fazer.
  timeout /t 3 >nul
  exit /b 0
)
if not exist "%PERFIL%" mkdir "%PERFIL%"
start "" "%CHROME%" --remote-debugging-port=9222 --remote-debugging-address=127.0.0.1 --user-data-dir="%PERFIL%" --no-first-run --no-default-browser-check "https://labs.google/fx/tools/flow"
echo Chrome do Flow aberto (porta 9222, perfil isolado em %PERFIL%).
timeout /t 3 >nul
endlocal
