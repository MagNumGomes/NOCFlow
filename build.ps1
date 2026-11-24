param([switch]$SemAtalho, [switch]$SomentePacote, [string]$PastaSaida = "dist", [string]$PythonBuild = "")

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$pastaDist = if ([System.IO.Path]::IsPathRooted($PastaSaida)) { $PastaSaida } else { Join-Path $raiz $PastaSaida }
if (-not $PythonBuild) { $PythonBuild = Join-Path $raiz ".venv-build\Scripts\python.exe" }

function Confirmar-Sucesso([string]$etapa) {
    if ($LASTEXITCODE -ne 0) {
        throw "Falha em: $etapa (codigo $LASTEXITCODE)."
    }
}

Write-Host "Preparando ambiente isolado de build..."
if (-not (Test-Path $pythonBuild)) {
    & python -m venv (Join-Path $raiz ".venv-build")
    Confirmar-Sucesso "criar ambiente Python"
}

& $pythonBuild -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple -r (Join-Path $raiz "scripts\requirements-windows.txt")
Confirmar-Sucesso "instalar dependencias de build"
& $pythonBuild -m pip check
Confirmar-Sucesso "validar dependencias instaladas"
& $pythonBuild (Join-Path $raiz "scripts\versionar.py") --check
Confirmar-Sucesso "validar versao e artefatos gerados"

Write-Host "Gerando executavel Windows com a extensao do Edge..."
$destino = Join-Path $pastaDist "NOCFlow"
$executavel = Join-Path $destino "NOCFlow.exe"
$emUso = Get-Process -Name "NOCFlow" -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $executavel }
if ($emUso) { throw "Feche o NOCFlow em $destino antes de substituir esse executavel." }
& $pythonBuild (Join-Path $raiz "scripts\gerar_userscripts.py")
Confirmar-Sucesso "gerar userscripts Tampermonkey"
& $pythonBuild -m PyInstaller --noconfirm --clean --distpath $pastaDist --workpath (Join-Path $raiz "build") (Join-Path $raiz "scripts\NOC.spec")
Confirmar-Sucesso "empacotar aplicativo"

if ($env:NOCFLOW_SIGN_CERT_THUMBPRINT) {
    $cert = Get-Item "Cert:\CurrentUser\My\$env:NOCFLOW_SIGN_CERT_THUMBPRINT"
    $assinatura = Set-AuthenticodeSignature -FilePath $executavel -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com"
    if ($assinatura.Status -ne 'Valid') { throw 'Assinatura Authenticode invalida.' }
}
if ($env:GITHUB_REF_TYPE -eq 'tag' -and (Get-AuthenticodeSignature $executavel).Status -ne 'Valid') {
    throw 'Release exige certificado Authenticode provisionado e assinatura valida.'
}
& $pythonBuild (Join-Path $raiz "scripts\inventario_release.py") --pacote $destino
Confirmar-Sucesso "gerar SBOM e proveniencia"

Copy-Item (Join-Path $raiz "scripts\LEIA-ME-executavel.txt") $destino
Copy-Item (Join-Path $raiz "scripts\Abrir configuracoes.cmd") $destino
Copy-Item (Join-Path $raiz "README.md") $destino
Copy-Item (Join-Path $raiz "VERSION") $destino
Copy-Item (Join-Path $raiz "docs") $destino -Recurse -Force
Copy-Item (Join-Path $raiz "tampermonkey") $destino -Recurse -Force

# Confere dependencias nativas e navegador dentro do proprio executavel.
$relatorio = Join-Path $raiz "build\verificacao.json"
Write-Host "Verificando o executavel, a ponte local, a extensao e o Microsoft Edge..."
$processo = Start-Process -FilePath $executavel -ArgumentList @("--verificar-build", ('"' + $relatorio + '"')) -PassThru
if (-not $processo.WaitForExit(90000)) {
    $processo.Kill()
    throw "A verificacao do executavel excedeu 90 segundos."
}
if ($processo.ExitCode -ne 0) {
    if (Test-Path $relatorio) { Get-Content $relatorio }
    throw "O executavel nao passou na verificacao."
}

# Inicializa apenas os dados deste usuario; nunca entram no pacote distribuido.
if (-not $SomentePacote) {
$dadosUsuario = Join-Path $env:LOCALAPPDATA "NOCFlow"
New-Item -ItemType Directory -Path $dadosUsuario -Force | Out-Null
$envUsuario = Join-Path $dadosUsuario ".env"
if (-not (Test-Path $envUsuario)) {
    $envOrigem = Join-Path $raiz ".env.example"
    Copy-Item $envOrigem $envUsuario
}

if (-not $SemAtalho) {
    $shell = New-Object -ComObject WScript.Shell
    $desktop = $shell.SpecialFolders.Item("Desktop")
    $atalho = $shell.CreateShortcut((Join-Path $desktop "NOCFlow.lnk"))
    $atalho.TargetPath = $executavel
    $atalho.WorkingDirectory = $destino
    $atalho.Description = "NOCFlow"
    $atalho.IconLocation = "$executavel,0"
    $atalho.Save()
    Write-Host "Atalho criado na Area de Trabalho."
}
}

Write-Host ""
Write-Host "Build concluido: $executavel"
if (-not $SomentePacote) { Write-Host "Configuracao e dados: $dadosUsuario" }
Write-Host "Para distribuir, copie a pasta NOCFlow inteira."
