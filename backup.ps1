#!/usr/bin/env pwsh
# backup.ps1
# Faz um dump do banco (Supabase) usando pg_dump via Docker.
# Uso:  ./backup.ps1            (lê DATABASE_URL do .env)
#       ./backup.ps1 -Retention 30
param(
    [int]$Retention = 14
)

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $ProjectRoot '.env'

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw ".env não encontrado em $ProjectRoot"
}

function Get-EnvValue([string]$name) {
    $line = Get-Content -LiteralPath $EnvFile |
        Where-Object { $_ -match "^$([regex]::Escape($name))\s*=" } |
        Select-Object -First 1
    if (-not $line) { return $null }
    $value = ($line -split '=', 2)[1].Trim()
    return $value.Trim('"', "'")
}

$dbUrl = Get-EnvValue 'DATABASE_URL'
if (-not $dbUrl) { throw 'DATABASE_URL não configurada no .env' }
$dbUrl = $dbUrl -replace '^postgresql\+asyncpg://', 'postgresql://'

$ssl = Get-EnvValue 'DATABASE_SSL'
if ($ssl -and ($ssl.ToLower() -notin @('', 'disable', 'false', '0', 'off', 'none'))) {
    $sep = if ($dbUrl -match '\?') { '&' } else { '?' }
    $dbUrl = $dbUrl + $sep + "sslmode=require"
}

$backupDir = Join-Path $ProjectRoot 'backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$fileName = "backup_$stamp.dump"
$containerFile = "/backup/$fileName"

Write-Host "Gerando backup do banco..."
docker run --rm `
    -v "${backupDir}:/backup" `
    postgres:16-alpine `
    pg_dump $dbUrl -Fc -f $containerFile

if ($LASTEXITCODE -ne 0) {
    throw 'pg_dump falhou (docker). Confira o DATABASE_URL e se o Docker está rodando.'
}

Write-Host "Backup concluído: $backupDir\$fileName"

$stale = Get-ChildItem -LiteralPath $backupDir -Filter 'backup_*.dump' |
    Sort-Object Name -Descending |
    Select-Object -Skip $Retention
if ($stale) {
    $stale | Remove-Item
    Write-Host "Removidos $($stale.Count) backup(s) antigo(s). Mantendo os últimos $Retention."
}
