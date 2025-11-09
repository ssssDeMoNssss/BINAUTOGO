# =========================================
# PowerShell скрипт для безопасного пуша проекта на GitHub
# =========================================
# Путь к локальному проекту
$localPath = "E:\BINAUTOGO"

# Переходим в папку проекта
Set-Location $localPath

# Инициализируем Git-репозиторий, если он ещё не инициализирован
if (-not (Test-Path -Path ".git")) {
    git init
    Write-Host "Git-репозиторий инициализирован."
}

# Просим пользователя ввести GitHub username
$githubUser = Read-Host "Введите ваш GitHub username"

# Просим пользователя ввести имя репозитория
$repoName = Read-Host "Введите имя репозитория на GitHub (например GPUOptimizedAvatar)"

# Запрашиваем Personal Access Token (PAT)
$pat = Read-Host "Введите Personal Access Token (PAT)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($pat))

# Добавляем все файлы в индекс
git add .

# Делаем коммит
$commitMessage = Read-Host "Введите сообщение для коммита"
git commit -m $commitMessage

# Проверяем существующий origin и удаляем, если есть
if (git remote get-url origin 2>$null) {
    git remote remove origin
    Write-Host "Старый origin удалён."
}

# Собираем URL с помощью конкатенации
$remoteUrl = "https://" + $githubUser + ":" + $ptr + "@github.com/" + $githubUser + "/" + $repoName + ".git"

# Добавляем новый origin
git remote add origin $remoteUrl
Write-Host "Новый origin добавлен: $remoteUrl"

# Устанавливаем ветку main
git branch -M main
Write-Host "Ветка main установлена."

# Пушим изменения
Write-Host "Пушим на GitHub..."
git push -u origin main
Write-Host "✅ Пуш завершён!"
