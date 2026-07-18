@echo off
REM Polls Kaggle job status every 60s and downloads output when COMPLETE.
setlocal
set KERNEL=alonsoalviraaaa/wildfire-front-training
set OUTDIR=c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output
set LOGFILE=c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output\monitor.log

:loop
for /f "delims=" %%i in ('kaggle kernels status %KERNEL% 2^>^&1') do set STATUS=%%i
echo [%date% %time%] %STATUS% >> "%LOGFILE%"

echo %STATUS% | find "COMPLETE" >nul 2>&1
if %errorlevel% equ 0 (
    echo [%date% %time%] Job COMPLETE - downloading output... >> "%LOGFILE%"
    kaggle kernels output %KERNEL% -p "%OUTDIR%" >> "%LOGFILE%" 2>&1
    echo [%date% %time%] Output downloaded to %OUTDIR% >> "%LOGFILE%"
    echo DONE >> "%LOGFILE%"
    exit /b 0
)

echo %STATUS% | find "ERROR" >nul 2>&1
if %errorlevel% equ 0 (
    echo [%date% %time%] Job ERROR - check Kaggle logs >> "%LOGFILE%"
    echo FAILED >> "%LOGFILE%"
    exit /b 1
)

ping -n 61 127.0.0.1 >nul 2>&1
goto loop