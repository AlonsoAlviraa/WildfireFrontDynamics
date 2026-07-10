@echo off
setlocal
set LOG=c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output\monitor2.log
set OUTDIR=c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output

:LOOP
for /f "tokens=2 delims=:," %%a in ('kaggle kernels status alonsoalviraaaa/wildfire-front-training 2^>^&1 ^| findstr "status"') do set STATUS=%%a
echo [%date% %time%] Status: %STATUS% >> "%LOG%"

echo %STATUS% | findstr /i "COMPLETE ERROR CANCEL" >nul
if %errorlevel% equ 0 (
    echo [%date% %time%] Job finished. Downloading output... >> "%LOG%"
    kaggle kernels output alonsoalviraaaa/wildfire-front-training -p "%OUTDIR%" >> "%LOG%" 2>&1
    echo [%date% %time%] Download complete. >> "%LOG%"
    exit /b 0
)

timeout /t 120 /nobreak >nul
goto LOOP