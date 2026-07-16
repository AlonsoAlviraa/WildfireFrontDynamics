@echo off
REM Usage: monitor2.bat [kernel_slug] [output_dir]
set KERNEL=%1
set OUTDIR=%2
if "%KERNEL%"=="" set KERNEL=alonsoalviraaaa/wildfire-front-training-v18
if "%OUTDIR%"=="" set OUTDIR=c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_outputs_v18
set LOG=%OUTDIR%\monitor2.log

if not exist "%OUTDIR%" mkdir "%OUTDIR%"

:loop
for /f "delims=" %%i in ('kaggle kernels status %KERNEL% 2^>^&1') do set STATUS=%%i
echo [%date% %time%] %STATUS% >> "%LOG%"

echo %STATUS% | findstr /i "COMPLETE ERROR CANCEL" >nul
if %errorlevel% equ 0 (
    echo [%date% %time%] Job finished. Downloading output... >> "%LOG%"
    kaggle kernels output %KERNEL% -p "%OUTDIR%" >> "%LOG%" 2>&1
    echo [%date% %time%] Download complete. >> "%LOG%"
    exit /b 0
)

ping -n 121 127.0.0.1 >nul 2>&1
goto loop