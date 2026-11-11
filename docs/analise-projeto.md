# Análise técnica e organização — NOCFlow

Revisão realizada em 21/10/2026 sobre o conteúdo local, incluindo as alterações que já existiam no diretório de trabalho.

Este é um registro histórico da revisão. Para a referência atual, consulte a [arquitetura](arquitetura.md) e o [manual de uso](../manual.md).

## Diagnóstico

O projeto implementa um aplicativo Windows local, com interface Tkinter, OCR nativo, fila persistente e extensão Edge Manifest V3. A integração opera sobre a sessão existente do navegador. Groq e Gemini são complementos opcionais ao fluxo local.

Foram revisados os módulos Python, JavaScript próprio, manifesto, gerador de userscripts, dependências, testes, configuração de empacotamento e documentação. Os artefatos gerados foram inventariados; `html2canvas` é uma biblioteca de terceiros, distribuída com sua licença, e não foi reescrita.

**Pontos fortes identificados:**

- Separação entre operações demoradas e a thread da interface por workers e filas.
- Importação validada antes de aplicar o lote; identidade por instância/eventid e UUID local para correlacionar tickets.
- Persistência atômica, migração de rascunhos antigos e backup de arquivos inválidos.
- Ponte restrita ao loopback, tokens temporários, verificação de Host e validação da origem/rota do ticket.
- Fluxo principal sem chamadas pagas; cache limitado e uso de IA explicitamente configurável.
- Fontes compartilhadas entre extensão e userscripts, com verificação de correspondência dos artefatos.

Os principais problemas estavam na concentração de responsabilidades, em caminhos antigos de execução e em divergências entre comportamento e documentação.

## Organização aplicada

O código de execução está no pacote `noc/`. `app_noc.py` é a entrada estável para executar pelo Python e pelo PyInstaller.

| Responsabilidade | Local |
|---|---|
| Interface e eventos | `noc/interface.py` |
| Configuração e caminhos de recursos/dados | `noc/configuracao.py` |
| Importação e fila de incidentes | `noc/incidentes.py` |
| Persistência e recuperação | `noc/rascunhos.py` |
| Coordenação OCR e IA | `noc/extracao.py` |
| Interpretação local e cache | `noc/extracao_local.py` |
| OCR espacial do Windows | `noc/ocr_windows.py` |
| Pedidos e retorno do Movidesk | `noc/movidesk.py` |
| Ponte HTTP e instalação da extensão | `noc/edge_bridge.py` |
| Validação e templates | `noc/comunicados.py` |
| Clipboard nativo | `noc/clipboard_windows.py` |
| Recortes e editor de imagem | `noc/recortes_email.py` |
| Consumo de tokens | `noc/tokens_ia.py` |

`noc_services.py`, antes com 714 linhas e responsabilidades distintas, foi substituído pelos módulos específicos. Os imports, testes e empacotamento usam diretamente esses módulos. A interface passou a se chamar `NOCFlow`, coerente com o produto.

As dependências foram divididas em execução (`requirements.txt`), desenvolvimento (`requirements-dev.txt`) e build (`requirements-build.txt`). Ruff verifica erros sintáticos, nomes indefinidos e imports/variáveis sem uso. `.env.example` passou a ser a fonte das opções adicionadas a configurações existentes.

## Problemas corrigidos

| Problema observado | Correção |
|---|---|
| **Ler print** reutilizava a imagem antiga mesmo após nova captura | O botão lê o clipboard atual; releitura e complementação usam a imagem guardada. |
| Uma nova captura podia substituir a evidência do incidente anterior antes de reconhecer outro evento | A imagem fica pendente até aplicar o resultado. Outro host/alerta recebe novo incidente, sem herdar severidade, horário ou ticket antigos. |
| Resposta parcial da Groq encerrava a extração antes da visão | Apenas os campos ainda vazios seguem para Gemini, quando configurado. |
| Snapshots compartilhavam listas/dicionários internos de metadados | Cópias independentes evitam alterações durante o salvamento. |
| Fila restaurada aceitava campos opcionais ausentes sem normalização | Os campos do formulário e a imagem são normalizados antes do uso pela interface. |
| Uma fila vazia/inválida no arquivo podia ser tratada como rascunho antigo | Fila presente é validada, permitindo acionar o mecanismo existente de preservação do arquivo inválido. |
| Número encontrado no modal era enviado com `/Ticket/Create`, incompatível com a validação da ponte | A extensão monta a URL de edição na instância autorizada e mantém a validação do ID. |
| Modal inicialmente oculto podia passar despercebido ao ser exibido | O observador acompanha também mudanças de classe, estilo, visibilidade e texto. |
| Trechos anteriores à assinatura podiam desaparecer e o texto do alerta era usado para inferir preenchimento anterior | Conteúdo existente é preservado; um marcador específico evita duplicação. |
| Editor `contenteditable` genérico era localizado, mas não preenchido | Foi implementado o preenchimento com os eventos de edição correspondentes. |
| Consulta Select2 usava AJAX síncrono | Consulta assíncrona com timeout de 5 segundos. |
| `html2canvas` carregava em toda página Zabbix | Manifesto carrega somente os coletores; biblioteca é solicitada quando uma imagem é necessária. |
| Playwright e seu driver eram distribuídos apesar de não participarem do fluxo do aplicativo | Dependência restrita ao desenvolvimento; verificação empacotada confere a instalação do Edge. |
| Build encerrava processos do aplicativo à força | Build verifica se o destino está aberto e solicita seu fechamento normal. |
| URLs com portas inválidas e imagens com tipos não textuais podiam passar pela validação | Validação de URL centralizada e validação explícita do campo de imagem. |

## Remoções e limpeza

- Parser antigo `interpretar_resposta`, que só era chamado por um teste e não participava da extração atual.
- Aliases antigos `GeradorIA_NOC`, `btn_ia` e `preencher_movidesk_playwright`.
- Método de navegação usado apenas pelos testes; estes agora exercitam o seletor real da interface.
- Caminho não utilizado de envio de imagem como string no gerador de HTML; o fluxo utiliza imagens PIL decodificadas na importação.
- Coleta do driver Playwright e filtros de navegadores que só existiam para esse empacotamento.
- Import sem uso e chamada obsoleta do Pillow nos testes.

Também foram removidos os builds intermediários `dist/email-recortes`, `dist/extensao-edge`, `dist/groq-reserva`, `dist/local-first`, `dist/OrquestradorNOC`, `dist/simplificada` e `dist/tokens-apis`. O pacote anterior de `dist/NOCFlow` foi substituído pelo novo executável validado, mantendo o destino do atalho existente. Caches Python/Ruff e os intermediários do PyInstaller foram limpos; o relatório de verificação foi mantido.

A redução líquida é de aproximadamente **2 GiB**. A conferência das pastas de distribuição não encontrou `.env` nem `rascunho.json` nesses builds. Configurações, rascunhos, o perfil antigo `movidesk_profile/` e o ambiente utilizado para build foram preservados como dados/recursos locais.

As cópias Tampermonkey são artefatos de distribuição intencionais, gerados a partir de `edge_extension/`. A biblioteca `html2canvas` e sua licença também são necessárias.

## Verificação

- Suíte inicial: **63 testes**, com **60 aprovados e 3 de navegador desativados**.
- Após a reorganização: **68 testes aprovados** em uma execução completa, incluindo navegador, extensão, OCR nativo e interface gráfica. Após o ajuste final do observador, os **3 testes Movidesk** passaram novamente, incluindo o novo caso Select2: **69 testes distintos verificados** ao todo.
- Ruff: sem erros nas regras configuradas.
- `pip check`: sem incompatibilidades declaradas nas dependências instaladas.
- Build Windows e verificação offline do executável: aprovados; pacote final em `dist/NOCFlow`, com extensão atualizada, e relatório em `build/verificacao.json`.
- Pacote distribuível: **281,08 MiB → 177,89 MiB**, redução de aproximadamente **36,7%**, principalmente pela retirada do Playwright.

As verificações usam fixtures locais e respostas simuladas dos provedores. O OCR foi executado de fato no Windows e a extensão foi carregada em Chromium. O teste do executável verifica interface, OCR, importação, recortes, SDKs, ponte, recursos da extensão e presença do Edge.

## Manutenção recomendada

1. **Migrar o SDK Gemini legado.** A versão instalada de `google-generativeai` informa oficialmente o encerramento de suporte. A migração para `google-genai` exige adaptar schemas, tratamento de erros, metadados de consumo e hooks do build. O ponto de integração agora está isolado em `noc/extracao.py`.
2. **Homologar seletores nos layouts reais.** Os testes cobrem HTML controlado, editores, categorias, urgência, assinatura, modal e retorno fora de ordem. Instâncias Movidesk/Zabbix podem alterar componentes e rotas; consulte o roteiro do [manual](../manual.md) e a referência de [arquitetura](arquitetura.md).
3. **Fixar o ambiente completo de releases.** As constraints atuais fixam a cadeia legada do Gemini, mas outras dependências ainda aceitam faixas. Um lock completo deve ser produzido a partir do ambiente de release homologado.
4. **Continuar reduzindo a interface conforme ela crescer.** O controlador Tkinter ainda concentra construção visual e despacho de eventos. Persistência, configuração, extração e integração já estão isoladas, permitindo separar as abas sem alterar os serviços.

## Rotina de desenvolvimento

```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m playwright install chromium --no-shell
$env:NOC_TEST_BROWSER = "1"
python -m unittest discover -s tests -v
python gerar_userscripts.py
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

Edite os coletores em `edge_extension/` e regenere os userscripts. Recursos estáticos são resolvidos pela raiz do projeto ou por `_internal` no executável. Dados do usuário continuam em `.env`/`.noc_data` na execução pelo Python e em `%LOCALAPPDATA%\NOCFlow` na execução empacotada.
