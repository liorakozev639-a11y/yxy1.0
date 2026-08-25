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

$taskItem = $generated.data.plan.items |
  Where-Object { $_.kind -eq "task" } |
  Select-Object -First 1
if ($null -eq $taskItem) {
  throw "生成的计划中没有可执行任务"
}

$executionNow = [DateTimeOffset]::Now.ToString("o")
$executionBody = @{ now = $executionNow } | ConvertTo-Json
Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/plans/$($generated.data.plan.plan_id)/items/$($taskItem.id)/execution/start" `
  -ContentType "application/json" `
  -Body $executionBody | Out-Null

Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/plans/$($generated.data.plan.plan_id)/items/$($taskItem.id)/execution/complete" `
  -ContentType "application/json" `
  -Body $executionBody | Out-Null

$refresh = Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/plans/$($generated.data.plan.plan_id)/execution/refresh"

$reflection = Invoke-RestMethod -Method Post `
  -Uri "$BaseUrl/api/v1/plans/$($generated.data.plan.plan_id)/items/$($taskItem.id)/reflection" `
  -ContentType "application/json" `
  -Body '{"sentiment":"satisfied"}'

$review = Invoke-RestMethod -Method Get `
  -Uri "$BaseUrl/api/v1/plans/$($generated.data.plan.plan_id)/review"

if ($reflection.data.sentiment -ne "satisfied") {
  throw "完成感受未保存"
}
if ($null -eq $review.data.summary) {
  throw "复盘摘要未返回"
}

[pscustomobject]@{
  session_id = $sessionId
  questionnaire_total = $questionnaire.data.total
  submitted = $submitted.data.submitted
  profile_rule = $generated.data.profile.rule_version
  covered_categories = $generated.data.recommendation.covered_categories
  plan_id = $generated.data.plan.plan_id
  plan_items = $generated.data.plan.items.Count
  restored_plan_id = $restoredPlan.data.plan_id
  reminder_count = $refresh.data.reminders.needs_adjustment_count
  review_status = $review.data.status
  reflection = $reflection.data.sentiment
} | ConvertTo-Json -Depth 8

Write-Output "Test session: $sessionId"
