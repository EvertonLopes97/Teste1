@echo off
REM DETTO — instala tudo num PC novo (rode dentro da pasta detto-premiere-bridge)
cd /d "%~dp0"
echo == Python ==
python --version || (echo Instale o Python 3.11 em python.org e marque "Add to PATH". & pause & exit /b 1)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo == Node ==
node --version || (echo Instale o Node 20 LTS em nodejs.org. & pause & exit /b 1)
call npm install
echo == FFmpeg ==
ffmpeg -hide_banner -filters | findstr /C:"zscale" >nul || (echo FALTA o FFmpeg "full" com zscale: winget install Gyan.FFmpeg  ^(depois feche e abra o PowerShell^) & pause & exit /b 1)
echo == Tesseract (opcional: 3a leitura de letra sem internet) ==
where tesseract >nul 2>nul || echo   opcional: winget install UB-Mannheim.TesseractOCR  ^(+ idioma portugues^)
echo.
echo Pronto. Agora:  setx GEMINI_API_KEY "SUA_CHAVE"   (feche e abra o PowerShell)
echo e depois:       python tools\painel\painel.py --instalar
pause
