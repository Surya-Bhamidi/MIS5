param([ValidateRange(1,8)][int]$Workers = 4)
$ErrorActionPreference = 'Stop'
$researchRoot = $PSScriptRoot
$workspaceRoot = Split-Path (Split-Path $researchRoot -Parent) -Parent
Push-Location $workspaceRoot
try {
    & python (Join-Path $researchRoot 'run_selective_fusion.py') --workers $Workers
    if ($LASTEXITCODE -ne 0) { throw 'Selective fusion experiment failed' }
    foreach ($script in @('verify_selective_fusion.py','report_selective_fusion.py')) {
        & python (Join-Path $researchRoot $script)
        if ($LASTEXITCODE -ne 0) { throw "Research script failed: $script" }
    }
} finally {
    Pop-Location
}
