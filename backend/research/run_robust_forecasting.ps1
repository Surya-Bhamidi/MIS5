$ErrorActionPreference = 'Stop'
$researchRoot = $PSScriptRoot
$workspaceRoot = Split-Path (Split-Path $researchRoot -Parent) -Parent
Push-Location $workspaceRoot
try {
    foreach ($script in @('run_robust_forecasting.py','context_baselines.py','rescore_robust_decisions.py','separated_alarm.py','verify_robust_forecasting.py','report_robust_forecasting.py')) {
        & python (Join-Path $researchRoot $script)
        if ($LASTEXITCODE -ne 0) { throw "Research script failed: $script" }
    }
} finally {
    Pop-Location
}
