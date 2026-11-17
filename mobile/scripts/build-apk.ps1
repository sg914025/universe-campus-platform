# Author: UniVerse Team. Rebuild the installable Android test client.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$configuration=Get-Content -LiteralPath (Join-Path $root 'config\project.json') -Raw -Encoding UTF8|ConvertFrom-Json
$backend=[System.IO.Path]::GetFullPath((Join-Path $root $configuration.backendPath))
$python=Join-Path $backend '.venv\Scripts\python.exe'
if($env:UNIVERSE_PYTHON){$python=$env:UNIVERSE_PYTHON}
if(-not(Test-Path -LiteralPath $python)){throw 'Python is missing. Set UNIVERSE_PYTHON to a Python executable.'}
$env:PYTHONUTF8='1'
& $python (Join-Path $root 'android\build_apk.py') --config (Join-Path $root 'config\project.json')
exit $LASTEXITCODE
