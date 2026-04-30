param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$repoRoot = $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$entry = Join-Path $repoRoot "main.py"

if (-not (Test-Path $entry)) {
    throw "未找到入口文件: $entry"
}

if (-not (Test-Path $python)) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "未找到 .venv\\Scripts\\python.exe，也未检测到系统 python。"
    }
    $python = $pythonCommand.Source
}

& $python $entry @CliArgs
exit $LASTEXITCODE
