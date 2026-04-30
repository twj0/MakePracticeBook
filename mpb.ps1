param(
    [string]$TargetDir = (Join-Path $PSScriptRoot "dist\mpb")
)

$resolved = [System.IO.Path]::GetFullPath($TargetDir)
if (-not (Test-Path $resolved)) {
    throw "Target directory not found: $resolved"
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$parts = @()
if ($userPath) {
    $parts = $userPath.Split(';', [System.StringSplitOptions]::RemoveEmptyEntries)
}

if ($parts -contains $resolved) {
    Write-Host "PATH already contains $resolved"
    return
}

$updated = if ($userPath) { "$userPath;$resolved" } else { $resolved }
[Environment]::SetEnvironmentVariable("Path", $updated, "User")
Write-Host "Added to user PATH: $resolved"
Write-Host "Open a new terminal and run: mpb --help"
