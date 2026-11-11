# NOCFlow

Aplicativo Windows para apoiar equipes de **Network Operations Center (NOC)** no registro, acompanhamento e comunicação de atendimentos. Centraliza alertas, evidências e próximos passos, reduzindo tarefas repetitivas entre o monitoramento e o chamado.

## Recursos

- Importação de eventos do Zabbix e preenchimento assistido de tickets no Movidesk pela extensão do Microsoft Edge.
- Atendimentos multicanal, fila de incidentes, histórico, regras por perfil e lembretes de acompanhamento.
- Agenda de rotinas, diário de bordo, passagem de turno e indicadores locais.
- Capturas com OCR e preparação de comunicados para Teams, WhatsApp e e-mail.
- IA opcional para estruturar relatos, consultar procedimentos com fontes e resumir registros.

O operador revisa os dados e confirma as ações. O fluxo principal funciona localmente, sem chaves de IA.

## Tecnologias

**Python 3.10+**, **Tkinter**, **Pillow**, **WinRT/Windows OCR** e persistência em **JSON**. Integração com o navegador em **JavaScript**, extensão **Manifest V3** e ponte HTTP local. IA opcional com **Groq** e **Google Gemini**. Testes com **unittest** e **Playwright**, análise com **Ruff** e empacotamento com **PyInstaller**.

## Executar

Requer Windows 10/11 e Microsoft Edge.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe app_noc.py
```

Configure sua instância em `MOVIDESK_URL` no `.env`. Os domínios Zabbix publicados são demonstrativos: ajuste `edge_extension/manifest.json`, a lista `ZABBIX` em `edge_extension/background.js` e, se utilizar Tampermonkey, `gerar_userscripts.py` e execute o gerador. Instale a extensão pelo menu do aplicativo. Perfis operacionais e bases de conhecimento são carregados pela **Central operacional**.

## Testes e build

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
$env:NOC_TEST_BROWSER = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m ruff check .
.\build.ps1 -SemAtalho
```

O build gera `dist/NOCFlow/`; distribua a pasta completa. Credenciais, dados operacionais, perfis privados e artefatos locais ficam fora do Git.

Mais detalhes: [manual](manual.md) e [arquitetura](docs/arquitetura.md).
