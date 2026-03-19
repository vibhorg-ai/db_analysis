# Check all API endpoints against https://db-analyzer:9443
# Usage: .\check-api-endpoints.ps1
# Requires: curl.exe (or curl on PATH)

$Base = "https://db-analyzer:9443"
$Curl = "curl.exe"
$Accept = "Accept: application/json"

function Test-Endpoint {
    param([string]$Method, [string]$Path, [string]$Body = $null)
    $url = "$Base$Path"
    $curlArgs = @("-k", "-s", "-o", "NUL", "-w", "%{http_code}", "-H", $Accept, "-X", $Method)
    if ($Body) { $curlArgs += @("-H", "Content-Type: application/json", "-d", $Body) }
    $code = & $Curl @curlArgs $url 2>$null
    if (-not $code) { $code = "ERR" }
    return $code
}

Write-Host "Checking endpoints at $Base" -ForegroundColor Cyan
Write-Host ""

# Root / health (no /api prefix)
$rootEndpoints = @(
    @{ Method = "GET"; Path = "/health/live" },
    @{ Method = "GET"; Path = "/health/ready" },
    @{ Method = "GET"; Path = "/health" },
    @{ Method = "GET"; Path = "/metrics" }
)
Write-Host "--- Root / health ---" -ForegroundColor Yellow
foreach ($e in $rootEndpoints) {
    $code = Test-Endpoint -Method $e.Method -Path $e.Path
    $color = if ($code -eq "200") { "Green" } else { "Gray" }
    Write-Host ("  {0,-6} {1,-25} -> {2}" -f $e.Method, $e.Path, $code) -ForegroundColor $color
}

# GET /api/*
$getEndpoints = @(
    "/api/health",
    "/api/health/amaiz",
    "/api/connections",
    "/api/schema",
    "/api/index-recommendations",
    "/api/db-health",
    "/api/db-health/all",
    "/api/mcp-status",
    "/api/issues",
    "/api/insights",
    "/api/chat/session/validate"
)
Write-Host ""
Write-Host "--- GET /api/* ---" -ForegroundColor Yellow
foreach ($path in $getEndpoints) {
    $code = Test-Endpoint -Method "GET" -Path $path
    $color = if ($code -eq "200") { "Green" } elseif ($code -eq "401" -or $code -eq "403") { "DarkYellow" } else { "Gray" }
    Write-Host ("  GET    {0,-40} -> {1}" -f $path, $code) -ForegroundColor $color
}

# GET with query (session validate needs session_id; 404 is expected if invalid)
$code = Test-Endpoint -Method "GET" -Path "/api/chat/session/validate?session_id=test"
$color = if ($code -eq "200" -or $code -eq "404") { "Green" } else { "Gray" }
Write-Host ("  GET    {0,-40} -> {1}" -f "/api/chat/session/validate?session_id=test", $code) -ForegroundColor $color

# POST /api/* (minimal body; many may return 401/422)
$postEndpoints = @(
    @{ Path = "/api/connect"; Body = "{}" },
    @{ Path = "/api/connections/add"; Body = "{}" },
    @{ Path = "/api/analyze-query"; Body = '{"query":"SELECT 1"}' },
    @{ Path = "/api/sandbox"; Body = '{"query":"SELECT 1"}' },
    @{ Path = "/api/insights/run"; Body = "{}" },
    @{ Path = "/api/simulate"; Body = '{"change_type":"test"}' }
)
Write-Host ""
Write-Host "--- POST /api/* (minimal body) ---" -ForegroundColor Yellow
foreach ($e in $postEndpoints) {
    $code = Test-Endpoint -Method "POST" -Path $e.Path -Body $e.Body
    $color = if ($code -eq "200") { "Green" } elseif ($code -eq "201") { "Green" } elseif ($code -eq "401" -or $code -eq "403" -or $code -eq "422") { "DarkYellow" } else { "Gray" }
    Write-Host ("  POST   {0,-40} -> {1}" -f $e.Path, $code) -ForegroundColor $color
}

Write-Host ""
Write-Host "Done. 200 = success; 401/403 = auth; 422 = validation; 404 = not found." -ForegroundColor Cyan
