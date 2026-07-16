param(
    [string]$Kernel = "alonsoalviraaaa/wildfire-front-training-v19",
    [string]$OutDir = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_outputs_v19"
)

$log = Join-Path $OutDir "monitor2.log"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

while ($true) {
    $status = & kaggle kernels status $Kernel 2>&1 | Out-String
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$ts] $status"

    if ($status -match "COMPLETE|ERROR|CANCEL") {
        Add-Content -Path $log -Value "[$ts] Job finished. Downloading output..."
        & kaggle kernels output $Kernel -p $OutDir 2>&1 | Out-File -Append -FilePath $log
        Add-Content -Path $log -Value "[$ts] Download complete."
        break
    }
    Start-Sleep -Seconds 120
}