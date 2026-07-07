[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null

$base = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\data\real_if\raw_dropbox"
$organized = "$base\organized"
New-Item -ItemType Directory -Path $organized -Force | Out-Null

function Extract-Zip($zipPath, $destDir) {
    if (Test-Path $destDir) { Remove-Item $destDir -Recurse -Force }
    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    Write-Host "  Extracting to: $destDir"
    Expand-Archive -Path $zipPath -DestinationPath $destDir -Force
}

# 1. CARDOSO (from Transfer.zip - nested ZIPs)
Write-Host "`n=== Extracting CARDOSO ===" -ForegroundColor Yellow
$cardosoDir = "$organized\CARDOSO"
Extract-Zip "$base\20260707_transfer_02\Transfer.zip" "$organized\_temp_cardoso"
# Move nested ZIPs out and extract them
Get-ChildItem "$organized\_temp_cardoso\*.zip" | ForEach-Object {
    $subDir = "$cardosoDir\$([System.IO.Path]::GetFileNameWithoutExtension($_.Name))"
    Extract-Zip $_.FullName $subDir
    Remove-Item $_.FullName -Force
}
Remove-Item "$organized\_temp_cardoso" -Recurse -Force

# 2. LA ESTRELLA-ACOM1 (direct extraction)
Write-Host "`n=== Extracting LA ESTRELLA-ACOM1 ===" -ForegroundColor Yellow
Extract-Zip "$base\20260707_transfer_03\LA ESTRELLA-ACOM1.zip" "$organized\LA_ESTRELLA_ACOM1"

# 3. LA ESTRELLA-ACOM2 (direct extraction)
Write-Host "`n=== Extracting LA ESTRELLA-ACOM2 ===" -ForegroundColor Yellow
Extract-Zip "$base\20260707_transfer_04\LA ESTRELLA-ACOM2.zip" "$organized\LA_ESTRELLA_ACOM2"

# 4. Extract nested ZIPs from Transfer (2).zip (transfer_05) - unique fires
Write-Host "`n=== Extracting Transfer (2) nested fires ===" -ForegroundColor Yellow
Extract-Zip "$base\20260707_transfer_05\Transfer (2).zip" "$organized\_temp_multi"
Get-ChildItem "$organized\_temp_multi\*.zip" | ForEach-Object {
    $fireName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
    # Skip TOBARRA duplicate (already in transfer_01)
    if ($fireName -like "*TOBARRA*") {
        Write-Host "  SKIPPING duplicate: $fireName" -ForegroundColor DarkGray
        Remove-Item $_.FullName -Force
        return
    }
    $fireDir = "$organized\$fireName"
    Extract-Zip $_.FullName $fireDir
    Remove-Item $_.FullName -Force
}
Remove-Item "$organized\_temp_multi" -Recurse -Force

# 5. Clean up duplicate transfer_06 entirely
Write-Host "`n=== Removing duplicate transfer_06 ===" -ForegroundColor Yellow
Remove-Item "$base\20260707_transfer_06" -Recurse -Force
Write-Host "  Removed transfer_06 (exact duplicate of transfer_05)"

# Final inventory
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "FINAL ORGANIZED INVENTORY" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Get-ChildItem $organized -Directory | ForEach-Object {
    $files = Get-ChildItem $_.FullName -Recurse -File
    $sizeMB = [math]::Round(($files | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
    $tifs = ($files | Where-Object { $_.Extension -eq '.tif' }).Count
    $jpgs = ($files | Where-Object { $_.Extension -eq '.jpg' }).Count
    $kmzs = ($files | Where-Object { $_.Extension -eq '.kmz' }).Count
    Write-Host "`n$($_.Name):"
    Write-Host "  Files: $($files.Count) | Size: ${sizeMB} MB"
    Write-Host "  TIF: $tifs | JPG: $jpgs | KMZ: $kmzs"
}