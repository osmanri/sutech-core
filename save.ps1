param(
    [string]$msg = ""
)

if ([string]::IsNullOrWhiteSpace($msg)) {
    $dateStr = Get-Date -Format "yyyy-MM-dd HH:mm"
    $msg = "chore: update $dateStr"
}

Write-Host ""
Write-Host "[1/3] Проверка статуса..." -ForegroundColor Cyan
git status -s

Write-Host ""
Write-Host "[2/3] Добавление файлов и коммит: `"$msg`"..." -ForegroundColor Cyan
git add .
git commit -m "$msg"

Write-Host ""
Write-Host "[3/3] Отправка на GitHub..." -ForegroundColor Cyan
git push origin main

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
