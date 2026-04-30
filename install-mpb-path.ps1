param(
    [string]$TargetDir = $PSScriptRoot
)

$resolved = [System.IO.Path]::GetFullPath($TargetDir)
if (-not (Test-Path $resolved)) {
    throw "目标目录不存在: $resolved"
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if ($userPath) {
    $parts = $userPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
}

$pathAlreadyPresent = $parts -contains $resolved
if (-not $pathAlreadyPresent) {
    $updated = if ($userPath) { "$userPath;$resolved" } else { $resolved }
    [Environment]::SetEnvironmentVariable("Path", $updated, "User")
}

$profilePath = $PROFILE.CurrentUserCurrentHost
$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

$startMarker = "# >>> MakePracticeBook mpb >>>"
$endMarker = "# <<< MakePracticeBook mpb <<<"
$shimBlock = @"
$startMarker
function global:mpb {
    & '$resolved\mpb.ps1' @args
}
$endMarker
"@

$profileContent = if (Test-Path $profilePath) {
    Get-Content -Path $profilePath -Raw -Encoding UTF8
} else {
    ""
}

$pattern = "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))"
if ($profileContent -match $pattern) {
    $profileContent = [regex]::Replace($profileContent, $pattern, $shimBlock)
} else {
    if ($profileContent -and -not $profileContent.EndsWith("`n")) {
        $profileContent += "`r`n"
    }
    $profileContent += $shimBlock
}

Set-Content -Path $profilePath -Value $profileContent -Encoding UTF8

if ($pathAlreadyPresent) {
    Write-Host "用户 PATH 中已包含: $resolved"
} else {
    Write-Host "已加入用户 PATH: $resolved"
}
Write-Host "已写入 PowerShell 配置文件: $profilePath"
Write-Host "请重新打开终端后运行: mpb -h"
