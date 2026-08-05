param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-AgentApi {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("GET", "POST", "PUT", "PATCH", "DELETE")]
        [string]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [hashtable]$Body
    )

    $parameters = @{
        Method      = $Method
        Uri         = "$BaseUrl$Path"
        ErrorAction = "Stop"
    }
    if ($null -ne $Body) {
        $parameters.ContentType = "application/json; charset=utf-8"
        $parameters.Body = $Body | ConvertTo-Json -Depth 5 -Compress
    }
    Invoke-RestMethod @parameters
}

$created = Invoke-AgentApi -Method POST -Path "/api/v1/sessions"
$sessionId = $created.data.session_id

$preferences = @{
    categories     = @("energy", "calm")
    duration       = "half"
    budget         = "low"
    outing         = "home"
    company        = "solo"
    city_or_campus = $null
    rest_only      = $true
}
Invoke-AgentApi -Method PUT `
    -Path "/api/v1/sessions/$sessionId/preferences" `
    -Body $preferences | Out-Null

$started = Invoke-AgentApi -Method POST `
    -Path "/api/v1/sessions/$sessionId/questionnaire/start" `
    -Body @{ mode = "quick" }
$questionId = $started.data.questions[0].id

Invoke-AgentApi -Method PATCH `
    -Path "/api/v1/sessions/$sessionId/questionnaire/answers/$questionId" `
    -Body @{ value = 4 } | Out-Null

$progress = Invoke-AgentApi -Method GET `
    -Path "/api/v1/sessions/$sessionId/questionnaire/progress"

[pscustomobject]@{
    session_id     = $sessionId
    question_id    = $questionId
    mode           = $progress.data.mode
    total          = $progress.data.total
    answered_count = $progress.data.answered_count
} | ConvertTo-Json -Compress
