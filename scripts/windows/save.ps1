param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$msg
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$commitMessage = ""
if ($msg -and $msg.Count -gt 0) {
    $commitMessage = $msg -join " "
}

# Clean any surrounding escaped quotes
$commitMessage = $commitMessage.Trim('"', "'", "\", " ")

if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    $dateStr = Get-Date -Format "yyyy-MM-dd HH:mm"
    $commitMessage = "chore: update $dateStr"
}

$frontendDir = Join-Path $PSScriptRoot "frontend"
if (Test-Path (Join-Path $frontendDir ".git")) {
    $feStatus = git -C $frontendDir status --porcelain
    if ($feStatus) {
        Write-Host ""
        Write-Host "[Frontend] Обнаружены изменения, сохранение..." -ForegroundColor Cyan
        git -C $frontendDir add .
        git -C $frontendDir commit -m "$commitMessage"
        git -C $frontendDir push origin main
    }
}

Write-Host ""
Write-Host "[1/3] Проверка статуса..." -ForegroundColor Cyan
git -C $PSScriptRoot status -s

Write-Host ""
Write-Host "[2/3] Добавление файлов и коммит: `"$commitMessage`"..." -ForegroundColor Cyan
git -C $PSScriptRoot add .
$rootStatus = git -C $PSScriptRoot status --porcelain
if ($rootStatus) {
    git -C $PSScriptRoot commit -m "$commitMessage"
} else {
    Write-Host "Нет новых изменений для коммита в основном репозитории." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[3/3] Отправка на GitHub..." -ForegroundColor Cyan
git -C $PSScriptRoot push origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Green
    Write-Host " [OK] Все изменения успешно сохранены и отправлены!" -ForegroundColor Green
    Write-Host "========================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host " [!] Произошла ошибка при отправке в Git." -ForegroundColor Red
}
Write-Host ""

