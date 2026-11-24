# Manual de Uso — NOCFlow

Este manual apresenta de forma direta como instalar, configurar e operar o **NOCFlow** no dia a dia do plantão.

- **Apresentação do projeto:** [README](../README.md)
- **Documentação técnica:** [Arquitetura](arquitetura.md)
- **Releases e CI:** [Dependências e Releases](releases.md)

---

## 1. Requisitos e Instalação

### Requisitos
- **Windows 10 ou 11** (com idioma Português ou Inglês instalado para o OCR nativo).
- **Microsoft Edge** logado no Zabbix, Movidesk e WhatsApp Web.
- *Opcional (apenas para rodar por código-fonte ou compilar):* **Python 3.12 x64**.

### Instalação do Aplicativo e da Extensão
1. **Aplicativo:** mantenha `NOCFlow.exe` dentro da pasta `NOCFlow` (ao lado de `_internal`) e abra o executável.
2. **Domínios HTTPS:**
   - Abra **`⋯` > `Configurações`** (`.env`) e defina `MOVIDESK_URL=https://suaempresa.movidesk.com`.
   - Edite `%LOCALAPPDATA%\NOCFlow\.noc_data\extensao.json` (ou `.noc_data\extensao.json` no código-fonte) com as URLs HTTPS do seu Zabbix em `"zabbix_origens"`, salve e reinicie o aplicativo.
3. **Extensão do Edge:**
   - Clique em **`⋯` > `Instalar extensão do Edge`**, copie o caminho e abra `edge://extensions/`.
   - Ative o **Modo do desenvolvedor**, clique em **Carregar sem compactação** e selecione a pasta copiada.
   - Atualize as abas abertas do Zabbix e do Movidesk com **F5**.

---

## 2. Visão Geral da Interface e Atalhos

| Elemento | Função |
|---|---|
| **Seletor no topo** | Alterna rapidamente entre os incidentes ativos da fila. |
| **Fila (N) / Voltar** | Abre a tabela da fila com busca, botão **Limpar filtros**, filtros por severidade/ticket/etapa e cores por criticidade (*Desastre*, *Alta*, *Média*, *Arquivado*). |
| **+ Novo** (`Ctrl+N`) | Cria um atendimento em branco sem perder os anteriores. |
| **Faixa Zabbix** | Exibe o status visual (`● conectado` em verde por **10 horas**, `▲ expirado/sem resposta` em âmbar, `○ desconectado`), botão **Conectar / Reconectar** e **Central operacional**. |
| **Aba Incidente** | Permite **Importar dados** (`Ctrl+I`), **Ler print** (`Ctrl+Shift+V`), revisar campos do alerta e abrir o evento no navegador pelo botão **`Abrir ↗`** ao lado do Link Zabbix. |
| **Aba Comunicar** | Botões rápidos de canal (**WhatsApp** `Alt+1`, **Teams** `Alt+2`, **E-mail** `Alt+3`) com indicador `✓` quando já copiado, seleção de modelo, destinatários por empresa e prévia com imagem. |
| **Aba Evidências** | Barra única para **Adicionar print**, **Ampliar**, **Recortar print**, **Copiar print** e **Copiar recorte**, além da escolha entre **Print completo** ou **Recorte**. |
| **Barra Inferior** | Campo **Ticket**, botão contextual (**Criar ticket**, **Voltar ao formulário**, **Abrir ticket #…**), **Copiar mensagem / Copiar e-mail** e **Próximo**. |

### Atalhos de Teclado
- **`Ctrl+N`**: Novo incidente.
- **`Ctrl+I`**: Importar JSON do Zabbix do clipboard.
- **`Ctrl+Shift+V`**: Ler print do clipboard com OCR local.
- **`Alt+1` / `Alt+2` / `Alt+3`**: Alternar canal para WhatsApp, Teams ou E-mail.
- **`Win+Shift+S`**: Capturar print da tela no Windows.
- **`Esc`**: Fechar janelas secundárias e diálogos modais.

---

## 3. Fluxo de Atendimento Passo a Passo

### Passo 1 — Conectar e Importar do Zabbix
1. Clique em **Conectar** no topo do NOCFlow. A conexão fica ativa por **10 horas**.
2. No Zabbix (página do evento `tr_events.php` ou lista `action=problem.view`), expanda o painel **`NOCFlow — Zabbix e Movidesk`** no canto inferior esquerdo.
3. Clique em **Enviar ao NOCFlow** (ou selecione até 100 linhas na lista e clique em **Enviar selecionados ao NOCFlow**).
   - O coletor envia os campos do alerta, as tags (como `Movidesk` para solicitante e tecnologia para serviço) e a imagem renderizada de *Host / Trigger / Severity*.

### Passo 2 — Abrir o Ticket no Movidesk
1. Revise os dados na aba **Incidente** e clique em **Criar ticket**.
2. O Edge abrirá o formulário do Movidesk, confirmará o tipo **Interno** e preencherá:
   - **Título:** `{alerta} - {servidor}`
   - **Descrição:** link do Zabbix + print da evidência + **1 linha em branco** antes da assinatura do analista.
   - **Classificação e Horas:** Categoria (`Alerta`), Urgência (`1` a `4`), Solicitante e Serviço (via tags), Tempo apontado (`00:03`) e Atividade (`Observability`).
3. Revise e clique em **Salvar** no Movidesk. O número gerado retorna sozinho para o campo **Ticket** do incidente no NOCFlow.

### Passo 3 — Comunicar (WhatsApp, Teams e E-mail)
1. Acesse a aba **Comunicar** e clique no botão do canal desejado (**WhatsApp**, **Teams** ou **E-mail**).
2. Escolha o **Modelo** (*Abertura normal*, *Abertura inicial*, *Acionamento inicial*, *Acionamento*, *Atualização*, *Cobrança*, *Passagem de turno*, *Normalização* ou *Encerramento*).
3. **No canal WhatsApp:** salve seu nome uma única vez para assinar automaticamente como `Seu Nome - Equipe NOC`.
4. **No canal E-mail:**
   - **Destinatários por Empresa:** cadastre empresas em **`+ Empresa`** (separando e-mails por `;`, vírgula ou quebra de linha). Se o nome da empresa constar no Servidor ou Alerta (ex.: `... - Manserv`), ela é selecionada automaticamente.
   - Clique em **`Copiar Para (N)`**, **`Copiar Cc (N)`** e **`Copiar assunto`** para colar nos campos do seu cliente de e-mail.
   - No rodapé da prévia, escolha rapidamente **`Anexo: Print completo`** ou **`Recorte`** (ou clique em **`Recortar`** para abrir o editor de 3 faixas: *Host*, *Trigger* e *Severity*).
   - Clique em **`Copiar e-mail`**: o NOCFlow copia o texto formatado com quebras de linha preservadas (`<br>` em HTML + texto puro) junto com a imagem da evidência logo abaixo.

---

## 4. Central Operacional

Clique em **Central operacional** no topo da janela para gerenciar o turno em 5 abas:

1. **Pendências:** lista todos os atendimentos ativos ordenados pelo prazo da próxima ação, destacando itens **`VENCIDA`** em vermelho. Duplo-clique abre o atendimento.
2. **Acompanhamento:** linha do tempo auditável do incidente, agendamento de follow-up (**Próxima ação**), avaliação determinística de regras de cliente (**Avaliar regra**), vínculo de **Referências** externas e **Organizar relato com IA**.
3. **Agenda:** cadastro de rotinas e verificações de dashboard do turno (*única*, *intervalo* ou *horários* com fuso e calendário). Rotinas vencidas ficam destacadas em vermelho e avisam no topo do aplicativo.
4. **Procedimentos e IA:** busca local instantânea em arquivos Markdown validados (`indice.json`) filtrados por perfil e serviço, com opção de resumo/explicação citando fontes (`[id]`).
5. **Diário e passagem:** geração de **Diário de bordo**, **Passagem de turno**, **Indicadores**, **Recorrência de tickets** e exportação direta para **CSV** ou **PDF**.

---

## 5. Utilitários no Navegador

- **No Zabbix:** além de enviar ao app, o painel oferece **`Copiar link + imagem`**, **`Copiar Trigger - Host`**, **`Copiar chamado reconhecido`** e **`Copiar imagem Host / Trigger / Severity`**.
- **No Movidesk:** painel no canto inferior esquerdo com **`Copiar número`**, **`Copiar ticket + assunto`** e **`Copiar template`** (número, assunto e link em linhas separadas).
- **No WhatsApp Web:** clique no ícone da extensão **NOCFlow** na barra do Edge, informe seu nome e clique em **`Assinar mensagem em edição`** para inserir `Nome - Equipe NOC` no topo da mensagem sem enviá-la.

---

## 6. Configurações (`.env`), Segurança e Backup

Abra **`⋯` > `Configurações`** para editar o `.env`:

| Variável | Padrão | Descrição |
|---|---|---|
| `MOVIDESK_URL` | `https://empresa.movidesk.com` | URL HTTPS base do Movidesk. |
| `NOME_OPERADOR` | vazio | Nome do operador usado nos comunicados e registros. |
| `MOVIDESK_LOGIN_TIMEOUT_SECONDS` | `120` | Tempo limite (5–300s) para abertura do formulário no Edge. |
| `MOVIDESK_RETORNO_TIMEOUT_SECONDS` | `28800` | Tempo limite (60–86400s, padrão 8h) aguardando salvar o ticket. |
| `OCR_TIMEOUT_SECONDS` | `15` | Timeout (5–300s) do OCR nativo do Windows. |
| `IA_EXTERNA_APROVADA` | `false` | Deve ser `true` para autorizar envio de texto redigido às APIs de IA (exige confirmação na janela de prévia a cada chamada). |
| `IA_AUTOMATICA` | `false` | Se `true` (e `IA_EXTERNA_APROVADA=true`), complementa lacunas do OCR automaticamente. |
| `GROQ_API_KEY` / `GEMINI_API_KEY` | vazio | Chaves opcionais migradas automaticamente na inicialização para `.noc_data/credenciais.dpapi` (criptografadas via Windows DPAPI). |
| `GROQ_MODEL` / `GEMINI_MODEL` | `openai/gpt-oss-120b` / `gemini-3.8-flash` | Modelos utilizados nas consultas opcionais de IA. |

### Onde ficam os dados locais
- **No Executável:** `%LOCALAPPDATA%\NOCFlow\` (`.env`, `.noc_data\rascunho.json` protegido com DPAPI, `.noc_data\destinatarios.json`, `.noc_data\extensao.json` e `.noc_data\logs\noc.jsonl`).
- **No Código-Fonte:** na raiz do projeto (`.env` e pasta `.noc_data\`).
- **Limpeza de rascunhos e logs:** `python scripts/limpar_dados_locais.py --diretorio "%LOCALAPPDATA%\NOCFlow"`.

---

## 7. Solução Rápida de Problemas

| Sintoma | Solução |
|---|---|
| **"Origem Zabbix não configurada"** | Adicione a URL HTTPS do Zabbix em `.noc_data/extensao.json`, reinicie o NOCFlow, clique em **Recarregar** em `edge://extensions/` e dê **F5** no Zabbix. |
| **Envio do Zabbix pede conexão** | Clique em **Conectar / Reconectar** na faixa superior do NOCFlow (a sessão dura 10 horas). |
| **Quebras de linha no e-mail** | Use sempre o botão **`Copiar e-mail`** na aba **Comunicar**; ele publica `HTML Format` com tags `<br>` explícitas e texto puro `\r\n`. |
| **Solicitante ou Serviço não preencheu** | Verifique se o evento no Zabbix possui a tag `Movidesk: <código>` e tag de tecnologia/serviço com correspondência única no Movidesk. |
| **Sem imagem ao clicar em Ler print** | Capture novamente com **`Win+Shift+S`** (copiar um arquivo do Explorer não coloca os pixels da imagem no clipboard). |
