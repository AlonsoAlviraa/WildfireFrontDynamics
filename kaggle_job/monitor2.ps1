$log = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output\monitor2.log"
$outdir = "c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\kaggle_output"

while ($true) {
    $status = & kaggle kernels status alonsoalvira/wildfire-front-training 2>&1 | Out-String
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $log -Value "[$ts] $status"

    if ($status -match "COMPLETE|ERROR|CANCEL") {
        Add-Content -Path $log -Value "[$ts] Job finished. Downloading output..."
        & kaggle kernels output alonsoalvira/wildfire-front-training -p $outdir 2>&1 | Out-File -Append -FilePath $log
        Add-Content -Path $log -Value "[$ts] Download complete."
        break
    }
    Start-Sleep -Seconds 120
}