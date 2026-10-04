$ErrorActionPreference = 'Stop'
$env:OMP_NUM_THREADS = '2'
$env:LOKY_MAX_CPU_COUNT = '2'
$researchRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $researchRoot
try {
    $researchCommands = @(
        @('backend/research/evidence_pilot.py', 'prepare'),
        @('backend/research/prepare_extended_data.py', 'darpa'),
        @('backend/research/prepare_extended_data.py', 'ait'),
        @('backend/research/evidence_pilot.py', 'checks'),
        @('backend/research/extended_study.py', 'ait'),
        @('backend/research/extended_study.py', 'darpa'),
        @('backend/research/fusion_study.py'),
        @('backend/research/sensor_stress.py', 'ait'),
        @('backend/research/sensor_stress.py', 'darpa'),
        @('backend/research/forecast_ablations.py'),
        @('backend/research/report_extended_study.py'),
        @('backend/research/verify_evidence_package.py')
    )
    foreach ($researchArguments in $researchCommands) {
        & python @researchArguments
        if ($LASTEXITCODE -ne 0) { throw "Research command failed: $researchArguments" }
    }
    & python -m unittest discover -s backend/tests
    if ($LASTEXITCODE -ne 0) { throw 'Application regression checks failed' }
} finally { Pop-Location }
