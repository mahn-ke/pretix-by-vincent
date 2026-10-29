param(
    [string]$CredentialFile = 'C:\Users\vm\pretix-runtime\credentials.json'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $CredentialFile)) { throw 'Private Pretix credentials are missing' }
$credentials = Get-Content $CredentialFile -Raw | ConvertFrom-Json
if (-not $credentials.database_password) { throw 'Database password is missing' }
$env:PRETIX_DB_PASSWORD = $credentials.database_password
Set-Location (Join-Path $PSScriptRoot '..')
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration is invalid' }
docker compose up -d --wait --pull never
if ($LASTEXITCODE -ne 0) { throw 'Pretix startup failed' }
