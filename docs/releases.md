# Dependências, CI e releases

## Verificação automática

`.github/workflows/ci.yml` roda em pushes/PRs para `dev` e `main`, manualmente e semanalmente. Usa Windows Server 2022 com Python 3.12 para Ruff, testes completos (Chromium, Tkinter e OCR), smoke por fonte e build PyInstaller com smoke do executável. O runner precisa de OCR inglês e Edge; ausência desses componentes deve falhar a homologação, não pular testes.

O job separado `Dependencias - pip-audit` consulta vulnerabilidades conhecidas do snapshot completo, sem instalar as bibliotecas Windows no Linux. Usa `--no-deps --disable-pip` porque as dependências transitivas já estão enumeradas e fixadas. Um alerta ou falha de consulta bloqueia o job; o JSON fica disponível como artefato. Isso não substitui revisão de código nem garante ausência de vulnerabilidades desconhecidas.

Actions são fixadas por SHA, com atualização pelo Dependabot. Os jobs de teste só têm leitura do repositório; apenas o job de publicação recebe escrita. Não há `pull_request_target`, merge automático ou execução de código do projeto no job com permissão de publicar.

## Snapshot homologado

`scripts/requirements-windows.txt` fixa execução, testes e ferramentas de build para Windows x64/Python 3.12. `requirements.txt` e `requirements-dev.txt` descrevem os requisitos funcionais; `scripts/constraints-build.txt` conserva as restrições do SDK Google legado. O CI instala esses arquivos juntos para detectar incompatibilidades.

O build usa o mesmo snapshot. Dependências de teste instaladas no ambiente de build são excluídas do pacote pelo PyInstaller. Isso estabiliza as versões Python; não promete binários idênticos bit a bit nem fixa o patch do Windows/Python ou o navegador.

Para validar uma atualização em ambiente limpo:

```powershell
python -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r scripts/requirements-windows.txt -r requirements-dev.txt -r scripts/requirements-build.txt
.\.venv-build\Scripts\python.exe -m pip check
$env:NOC_TEST_BROWSER = "1"
.\.venv-build\Scripts\python.exe -m playwright install chromium --no-shell
.\.venv-build\Scripts\python.exe -m unittest discover -s tests -v
.\.venv-build\Scripts\python.exe -m ruff check .
.\build.ps1 -SomentePacote
```

O Dependabot abre PRs semanais para `dev`, agrupando atualizações Python e Actions separadamente. Ao mudar uma dependência, atualize as constraints relacionadas e inclua no snapshot qualquer nova dependência transitiva. Não use `pip freeze` de um ambiente pessoal com pacotes alheios ao projeto. Rejeite atualizações com testes ou auditoria falhando.

O auditor é instalado separadamente a partir de `scripts/requirements-audit.txt`:

```powershell
python -m pip install -r scripts/requirements-audit.txt
python -m pip_audit -r scripts/requirements-windows.txt --no-deps --disable-pip
```

## Versão única e SemVer

`VERSION` é a fonte de verdade, no formato `MAJOR.MINOR.PATCH`:

- PATCH: correção compatível.
- MINOR: funcionalidade nova compatível.
- MAJOR: quebra de compatibilidade.

O aplicativo exibe a versão no título e no smoke. O arquivo acompanha o pacote. Para atualizar, edite `VERSION`, registre as mudanças em `CHANGELOG.md` e execute:

```powershell
python scripts/versionar.py
python scripts/versionar.py --check
```

O comando sincroniza o manifesto e os dois userscripts; o modo `--check` apenas verifica. O CI rejeita divergências. As versões são compartilhadas entre aplicativo, extensão e userscripts. Pré-releases com sufixo ainda não são suportadas pelo sincronizador, para manter compatibilidade com o manifesto do Edge.

## Publicação

1. Integre as mudanças de `dev` na `main` por PR com os checks aprovados.
2. No commit integrado, crie e envie uma tag anotada correspondente a `VERSION`:

```powershell
git tag -a v2.3.0 <SHA-integrado-na-main> -m "NOCFlow 2.3.0"
git push origin v2.3.0
```

3. `release.yml` executa novamente o pipeline de qualidade. Confere se a tag corresponde a `VERSION` e se o commit pertence ao histórico da `main`.
4. Somente após todos os jobs passarem, publica uma GitHub Release com ZIP completo, `SHA256SUMS.txt` e as notas daquela versão.

O pacote é gerado com `-SomentePacote`; `.env` real e `.noc_data` são rejeitados pelo empacotador. Distribua a pasta inteira, nunca só o executável. Uma tag enviada antes de integrar o commit à `main` falha. Não mova tags já publicadas: faça uma nova versão.

## Ativação no GitHub

Os arquivos entram em vigor após serem enviados ao GitHub. O agendamento semanal e a configuração do Dependabot precisam estar na branch padrão (`main`). A publicação só começa com o envio explícito de uma tag.

Em Settings → Branches, exija na `main` os checks `Windows - testes e build` e `Dependencias - pip-audit`, após aparecerem na primeira execução. Mantenha PR obrigatório e force-push desabilitado. Quando houver outro mantenedor, exija também aprovação de revisão. Configuração de proteção da branch não é alterada automaticamente por arquivos YAML.
