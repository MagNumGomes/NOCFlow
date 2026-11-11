param([switch]$SemAtalho, [string]$PastaSaida = "dist")

$ErrorActionPreference = "Stop"
$raiz = $PSScriptRoot
$pastaDist = if ([System.IO.Path]::IsPathRooted($PastaSaida)) { $PastaSaida } else { Join-Path $raiz $PastaSaida }
$pythonBuild = Join-Path $raiz ".venv-build\Scripts\python.exe"

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

& $pythonBuild -m pip install -r (Join-Path $raiz "requirements-build.txt")
Confirmar-Sucesso "instalar dependencias de build"

Write-Host "Gerando executavel Windows com a extensao do Edge..."
$destino = Join-Path $pastaDist "NOCFlow"
$executavel = Join-Path $destino "NOCFlow.exe"
$emUso = Get-Process -Name "NOCFlow" -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $executavel }
if ($emUso) { throw "Feche o NOCFlow em $destino antes de substituir esse executavel." }
& $pythonBuild (Join-Path $raiz "gerar_userscripts.py")
Confirmar-Sucesso "gerar userscripts Tampermonkey"
& $pythonBuild -m PyInstaller --noconfirm --clean --distpath $pastaDist --workpath (Join-Path $raiz "build") (Join-Path $raiz "NOC.spec")
Confirmar-Sucesso "empacotar aplicativo"

Copy-Item (Join-Path $raiz "LEIA-ME-executavel.txt") $destino
Copy-Item (Join-Path $raiz "Abrir configuracoes.cmd") $destino
Copy-Item (Join-Path $raiz "README.md") $destino
Copy-Item (Join-Path $raiz "manual.md") $destino
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
$dadosUsuario = Join-Path $env:LOCALAPPDATA "NOCFlow"
New-Item -ItemType Directory -Path $dadosUsuario -Force | Out-Null
$envUsuario = Join-Path $dadosUsuario ".env"
if (-not (Test-Path $envUsuario)) {
    $envOrigem = Join-Path $raiz ".env"
    if (-not (Test-Path $envOrigem)) { $envOrigem = Join-Path $raiz ".env.example" }
    Copy-Item $envOrigem $envUsuario
}
$rascunhoOrigem = Join-Path $raiz ".noc_data\rascunho.json"
$rascunhoDestino = Join-Path $dadosUsuario ".noc_data\rascunho.json"
if ((Test-Path $rascunhoOrigem) -and -not (Test-Path $rascunhoDestino)) {
    New-Item -ItemType Directory -Path (Split-Path $rascunhoDestino) -Force | Out-Null
    Copy-Item $rascunhoOrigem $rascunhoDestino
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

Write-Host ""
Write-Host "Build concluido: $executavel"
Write-Host "Configuracao e dados: $dadosUsuario"
Write-Host "Para distribuir, copie a pasta NOCFlow inteira."
