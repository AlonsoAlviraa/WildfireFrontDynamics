$content = Get-Content 'data\real_if\raw_dropbox\20260707_transfer_02\test_download.zip' -Raw

# Try to find direct download URLs - expanded patterns
$patterns = @(
    'https://[^\"''\s]+\.dropbox\.com[^\"''\s]*',
    '"download_url":"([^"]+)"',
    'href="(https://[^"]*)"',
    '"url":"([^"]*download[^"]*)"',
    '"transfer_id":"([^"]*)"',
    '"downloadLink":"([^"]*)"'
)

Write-Host "--- Searching for URLs and metadata ---"
foreach ($pattern in $patterns) {
    $m = [regex]::Matches($content, $pattern)
    if ($m.Count -gt 0) {
        Write-Host "FOUND ${m.Count} matches with pattern: $pattern"
        foreach ($match in $m) {
            Write-Host $match.Value
        }
        Write-Host ""
    }
}

# Search for JSON embedded data
Write-Host "--- Searching for embedded JSON data blocks ---"
$jsonMatches = [regex]::Matches($content, 'window\.__INITIAL[^=]*=\s*(\{.*?\});')
foreach ($m in $jsonMatches) { Write-Host $m.Groups[1].Value.Substring(0, [Math]::Min(500, $m.Groups[1].Value.Length)) }

# Search for script tags with data
Write-Host "--- Script src tags ---"
$scriptMatches = [regex]::Matches($content, 'src="([^"]*transfer[^"]*)"')
foreach ($m in $scriptMatches) { Write-Host $m.Groups[1].Value }

# Dump all https URLs
Write-Host "--- All HTTPS URLs in page ---"
$urlMatches = [regex]::Matches($content, 'https://[^\"''<>\s]+')
$unique = @{}
foreach ($m in $urlMatches) { if (-not $unique.ContainsKey($m.Value)) { $unique[$m.Value] = $true; Write-Host $m.Value } }

# Also look for filenames / metadata
Write-Host "`n--- Looking for filenames ---"
$fileMatches = [regex]::Matches($content, '"filename":"([^"]+)"')
foreach ($m in $fileMatches) { Write-Host $m.Groups[1].Value }

Write-Host "`n--- Looking for size ---"
$sizeMatches = [regex]::Matches($content, '"size":(\d+)')
foreach ($m in $sizeMatches) { Write-Host "Size: $($m.Groups[1].Value) bytes" }