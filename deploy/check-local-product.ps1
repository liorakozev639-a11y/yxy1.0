param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"

$apiHealth = Invoke-RestMethod "http://127.0.0.1:$BackendPort/health"
$dbHealth = Invoke-RestMethod "http://127.0.0.1:$BackendPort/api/v1/health/database"
$frontendStatus = (Invoke-WebRequest "http://127.0.0.1:$FrontendPort/" -UseBasicParsing).StatusCode
$manifestStatus = (Invoke-WebRequest "http://127.0.0.1:$FrontendPort/manifest.json?v=pwa-v1" -UseBasicParsing).StatusCode
$serviceWorkerStatus = (Invoke-WebRequest "http://127.0.0.1:$FrontendPort/service-worker.js" -UseBasicParsing).StatusCode

[PSCustomObject]@{
    ApiStatus = $apiHealth.data.status
    DatabaseStatus = $dbHealth.data.status
    FrontendStatusCode = $frontendStatus
    ManifestStatusCode = $manifestStatus
    ServiceWorkerStatusCode = $serviceWorkerStatus
    FrontendUrl = "http://127.0.0.1:$FrontendPort/"
    SwaggerUrl = "http://127.0.0.1:$BackendPort/docs"
} | ConvertTo-Json -Depth 5

