[System.Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem') | Out-Null

$base = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\data\real_if\raw_dropbox"

$zips = @(
    @{ path = "$base\20260707_transfer_02\Transfer.zip"; name = "Transfer.zip (transfer_02)" },
    @{ path = "$base\20260707_transfer_03\LA ESTRELLA-ACOM1.zip"; name = "LA ESTRELLA-ACOM1.zip (transfer_03)" },
    @{ path = "$base\20260707_transfer_04\LA ESTRELLA-ACOM2.zip"; name = "LA ESTRELLA-ACOM2.zip (transfer_04)" },
    @{ path = "$base\20260707_transfer_05\Transfer (2).zip"; name = "Transfer (2).zip (transfer_05)" },
    @{ path = "$base\20260707_transfer_06\Transfer (3).zip"; name = "Transfer (3).zip (transfer_06)" }
)

foreach ($z in $zips) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "ZIP: $($z.name)" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    try {
        $zip = [System.IO.Compression.ZipFile]::OpenRead($z.path)
        $entries = $zip.Entries
        Write-Host "Total entries: $($entries.Count)"

        # Show extensions breakdown
        $exts = @{}
        foreach ($e in $entries) {
            $ext = [System.IO.Path]::GetExtension($e.Name).ToLower()
            if (-not $exts.ContainsKey($ext)) { $exts[$ext] = 0 }
            $exts[$ext]++
        }
        Write-Host "`nExtensions breakdown:"
        $exts.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { Write-Host "  $($_.Key): $($_.Value)" }

        # Show first 15 entries (sample)
        Write-Host "`nFirst 15 entries:"
        $count = 0
        foreach ($e in $entries) {
            if ($count -ge 15) { break }
            Write-Host "  $($e.FullName) ($([math]::Round($e.Length/1KB, 1)) KB)"
            $count++
        }

        $zip.Dispose()
    } catch {
        Write-Host "ERROR opening: $_"
    }
}