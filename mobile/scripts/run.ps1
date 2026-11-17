# Author: UniVerse Team. Local build helper; never changes system settings.
param([ValidateSet('setup','build','preview')][string]$Action='build',[string]$Target='all',[switch]$Deploy)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new()
$projectRoot=Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$nodeCommand=Get-Command node -ErrorAction SilentlyContinue
$nodePath=if($nodeCommand){$nodeCommand.Source}else{Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'}
if(-not(Test-Path -LiteralPath $nodePath)){$nodePath=Join-Path $env:ProgramFiles 'nodejs\node.exe'}
if(-not(Test-Path -LiteralPath $nodePath)){throw 'Install Node.js 20 or newer, then try again.'}
if($Action -eq 'setup'){
 $npm=Join-Path $projectRoot '.tools\package\bin\npm-cli.js'
 if(Test-Path -LiteralPath $npm){& $nodePath $npm ci --no-audit --no-fund}else{
  $npmCommand=Get-Command npm.cmd -ErrorAction SilentlyContinue
  if(-not $npmCommand){throw 'npm is missing. Install Node.js with npm.'}
  & $npmCommand.Source ci --no-audit --no-fund
 }
}elseif($Action -eq 'preview'){
 $configuration=Get-Content -LiteralPath (Join-Path $projectRoot 'config\project.json') -Raw -Encoding UTF8|ConvertFrom-Json
 $env:UNIVERSE_DEV_BACKEND=$configuration.apiBase
 & $nodePath 'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js' --host 127.0.0.1
}else{
 $buildArgs=@('scripts/build.mjs',$Target)
 if($Deploy){$buildArgs+='--deploy'}
 & $nodePath @buildArgs
}
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
