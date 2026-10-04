param([switch]$FetchPublicEvidence)
$ErrorActionPreference = 'Stop'
$env:OMP_NUM_THREADS = '2'
$env:LOKY_MAX_CPU_COUNT = '2'
$researchRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Push-Location $researchRoot
try {
    if ($FetchPublicEvidence) {
        foreach ($script in @('fetch_endpoint_evidence.py','inspect_cam_archives.py','fetch_cam_evidence.py')) {
            & python "backend/research/$script"
            if ($LASTEXITCODE -ne 0) { throw "Evidence retrieval failed: $script" }
        }
    }
    foreach ($script in @('published_hmm_baseline.py','gru_baseline.py','audit_endpoints.py',
                         'cam_transfer.py','report_publication_validation.py','verify_publication_validation.py')) {
        & python "backend/research/$script"
        if ($LASTEXITCODE -ne 0) { throw "Supplemental study failed: $script" }
    }
} finally { Pop-Location }
