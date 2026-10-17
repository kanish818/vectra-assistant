param()
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
$root = (Get-Location).Path
New-Item -ItemType Directory -Path "docs\images" -Force | Out-Null

$shots = @(
  @{ name = "ui_answer_citation"; q = "What VPN server address should I use when working from home?" },
  @{ name = "ui_abstain";         q = "How do I get a parking pass for the Gurugram office?" },
  @{ name = "ui_pii_masked";      q = "Hi, I'm Anand Sharma (anand.sharma@vectralogistics.example, +91 9876543210). Company mail doesn't show up in my iPhone's built-in Mail app. How do I fix it?" },
  @{ name = "ui_injection_safe";  q = "My laptop is really slow, what should I do to speed it up?" }
)

$i = 0
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
foreach ($s in $shots) {
  $i++
  $q = [uri]::EscapeDataString($s.q)
  $out = Join-Path $root ("docs\images\" + $s.name + ".png")
  Remove-Item $out -ErrorAction SilentlyContinue
  $profile = Join-Path $env:TEMP "opencode\edge-shots\$stamp-$i"
  $eargs = @(
    "--headless=new", "--disable-gpu", "--hide-scrollbars",
    "--force-device-scale-factor=1", "--window-size=1150,1250",
    "--virtual-time-budget=60000",
    ("--user-data-dir=" + $profile),
    ("--screenshot=" + $out),
    ("http://localhost:8000/?q=" + $q)
  )
  $p = Start-Process -FilePath $edge -ArgumentList $eargs -Wait -PassThru -WindowStyle Hidden
  if (-not (Test-Path $out)) {
    Start-Sleep -Seconds 10
  }
  if (Test-Path $out) {
    Write-Output ("{0}  ->  {1} bytes (exit {2})" -f $s.name, (Get-Item $out).Length, $p.ExitCode)
  } else {
    Write-Output ("{0}  ->  FAILED (exit {1})" -f $s.name, $p.ExitCode)
  }
}
