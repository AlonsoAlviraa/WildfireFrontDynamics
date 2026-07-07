# Move ZIPs from Downloads to data/real_if/raw_dropbox/
$downloads = "$env:USERPROFILE\Downloads"
$base = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\data\real_if\raw_dropbox"

# Clean up test files from transfer_02
Remove-Item "$base\20260707_transfer_02\test_download.zip" -Force -ErrorAction SilentlyContinue
Remove-Item "$base\20260707_transfer_02\transfer_02.zip" -Force -ErrorAction SilentlyContinue

# Mapping: ZIP -> destination folder
$mappings = @(
    @{ src = "Transfer.zip";          dst = "20260707_transfer_02" },
    @{ src = "LA ESTRELLA-ACOM1.zip"; dst = "20260707_transfer_03" },
    @{ src = "LA ESTRELLA-ACOM2.zip"; dst = "20260707_transfer_04" },
    @{ src = "Transfer (2).zip";      dst = "20260707_transfer_05" },
    @{ src = "Transfer (3).zip";      dst = "20260707_transfer_06" }
)

foreach ($m in $mappings) {
    $srcPath = Join-Path $downloads $m.src
    $dstDir = Join-Path $base $m.dst
    $dstPath = Join-Path $dstDir $m.src

    Write-Host "Moving: $($m.src) -> $($m.dst)"

    # Create destination dir
    New-Item -ItemType Directory -Path $dstDir -Force | Out-Null

    if (Test-Path $srcPath) {
        # Move file
        Move-Item -Path $srcPath -Destination $dstPath -Force
        $size = [math]::Round((Get-Item $dstPath).Length / 1MB, 2)
        Write-Host "  OK - ${size} MB"
    } else {
        Write-Host "  WARNING: Source not found!"
    }
}

Write-Host "`n--- Final inventory in raw_dropbox ---"
Get-ChildItem -Path $base -Recurse -Filter "*.zip" | ForEach-Object {
    $rel = $_.FullName.Replace($base, "")
    $sizeMB = [math]::Round($_.Length / 1MB, 2)
    Write-Host "${rel}: ${sizeMB} MB"
}