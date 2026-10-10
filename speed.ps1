$adapters = Get-NetAdapter | Where-Object Status -eq "Up"
$totalBytes1 = 0
foreach ($a in $adapters) { $totalBytes1 += (Get-NetAdapterStatistics -Name $a.Name).ReceivedBytes }
Start-Sleep -Seconds 5
$totalBytes2 = 0
foreach ($a in $adapters) { $totalBytes2 += (Get-NetAdapterStatistics -Name $a.Name).ReceivedBytes }

$bytes = $totalBytes2 - $totalBytes1
$speedKB = [math]::Round($bytes / 5 / 1024, 2)
$speedMB = [math]::Round($speedKB / 1024, 2)
Write-Output "Total Speed: $speedKB KB/s ($speedMB MB/s)"
