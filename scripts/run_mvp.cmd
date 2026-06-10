@echo off
setlocal
cd /d "%~dp0\.."

python -m unittest discover -s tests -v
if errorlevel 1 exit /b %errorlevel%

python -m wildfire_front demo --output outputs\demo
if errorlevel 1 exit /b %errorlevel%

python scripts\generate_geotiff_fixture.py
if errorlevel 1 exit /b %errorlevel%

python -m wildfire_front ingest-geotiff --images outputs\geotiff-fixture\images --masks outputs\geotiff-fixture\masks --output outputs\geotiff-demo --event-id controlled_burn_demo --sensor-id thermal_demo --estimated-error-m 2.0
if errorlevel 1 exit /b %errorlevel%

echo.
echo MVP sintetico generado en outputs\demo\report.html
echo MVP GeoTIFF generado en outputs\geotiff-demo\report.html
