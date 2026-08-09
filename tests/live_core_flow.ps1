param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

$session = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/sessions"
$sessionId = $session.data.session_id

$preferences = @{
  categories = @("energy", "recovery", "social", "explore", "growth")
  duration = "half"
  budget = "high"
  outing = "home"
  company = "both"
  city_or_campus = "test-campus"
  rest_only = $false
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Put `
  -Uri "$BaseUrl/api/v1/sessions/$sessionId/preferences" `
  -ContentType "application/json" `
  -Body $preferences | Out-Null

$questionnaire = Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/sessions/$sessionId/questionnaire/start" `
  -ContentType "application/json" `
  -Body '{"mode":"quick"}'

foreach ($question in $questionnaire.data.questions) {
  Invoke-RestMethod -Method Patch `
    -Uri "$BaseUrl/api/v1/sessions/$sessionId/questionnaire/answers/$($question.id)" `
    -ContentType "application/json" `
    -Body '{"value":3}' | Out-Null
}

$submitted = Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/sessions/$sessionId/questionnaire/submit"

$freeStart = [DateTimeOffset]::Now.ToString("o")
$freeEnd = [DateTimeOffset]::Now.AddHours(4).ToString("o")
$generateBody = @{
  free_start = $freeStart
  free_end = $freeEnd
  density = "balanced"
} | ConvertTo-Json

$generated = Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/sessions/$sessionId/plan/generate" `
  -ContentType "application/json" `
  -Body $generateBody

$restoredPlan = Invoke-RestMethod -Method Get `
  -Uri "$BaseUrl/api/v1/sessions/$sessionId/plan"

[pscustomobject]@{
  session_id = $sessionId
  questionnaire_total = $questionnaire.data.total
  submitted = $submitted.data.submitted
  profile_rule = $generated.data.profile.rule_version
  covered_categories = $generated.data.recommendation.covered_categories
  plan_id = $generated.data.plan.plan_id
  plan_items = $generated.data.plan.items.Count
  restored_plan_id = $restoredPlan.data.plan_id
} | ConvertTo-Json -Depth 8

Write-Output "Test session: $sessionId"
