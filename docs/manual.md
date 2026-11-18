# Manual de Uso — NOCFlow

Este manual acompanha o operador desde a instalação até a comunicação de incidentes, o uso da **Central Operacional**, a geração de relatórios e a passagem de turno. A extensão e os painéis do navegador utilizam o nome **NOCFlow — Zabbix e Movidesk**.

Versão atual dos recursos de fluxo, extensão e interface: **2.2.3**.

Consulte também a [Apresentação do Projeto](../README.md) e a [Arquitetura Técnica](arquitetura.md).

## Sumário

- [Requisitos](#requisitos)
- [Instalação e atualização](#instalação-e-atualização)
- [Conhecer a interface](#conhecer-a-interface)
- [Atendimento de ponta a ponta](#atendimento-de-ponta-a-ponta)
- [Importar alertas do Zabbix](#importar-alertas-do-zabbix)
- [Organizar a fila](#organizar-a-fila)
- [Capturar imagens e usar OCR](#capturar-imagens-e-usar-ocr)
- [Preencher o Movidesk](#preencher-o-movidesk)
- [Preparar comunicados e recortes](#preparar-comunicados-e-recortes)
- [Central Operacional (Regras, Agenda, Conhecimento e Relatórios)](#central-operacional-regras-agenda-conhecimento-e-relatórios)
- [Utilitários do navegador e WhatsApp Web](#utilitários-do-navegador-e-whatsapp-web)
- [Configurar o aplicativo e a IA](#configurar-o-aplicativo-e-a-ia)
- [Acompanhar consumo e desempenho](#acompanhar-consumo-e-desempenho)
- [Dados, backup e encerramento](#dados-backup-e-encerramento)
- [Solução de problemas](#solução-de-problemas)

---

## Requisitos

- Windows 10 ou 11.
- Microsoft Edge, com acesso e login nas instâncias utilizadas de Zabbix e Movidesk.
- Português ou Inglês instalado no Windows para a leitura de imagens por OCR nativo.
- Python 3.10+ apenas quando executado pelo código-fonte ou para gerar um novo executável.

O fluxo principal funciona **100% localmente e sem chaves de IA**. O acesso aos sites depende da rede da organização; o processamento de capturas, fila, regras operacionais, relatórios e templates é local. A complementação por IA é opcional e exige conexão apenas com o provedor configurado (Groq e/ou Gemini).

---

## Instalação e atualização

### Usar o executável Windows

1. Copie a pasta `NOCFlow` completa para o computador.
2. Mantenha `NOCFlow.exe` e a subpasta `_internal` sempre juntos no mesmo diretório.
3. Abra `NOCFlow.exe` ou o atalho **NOCFlow**, se houver.
4. Aguarde a recuperação do rascunho e a mensagem de prontidão no rodapé.

O computador que recebe o pacote pronto não precisa de Python nem de editor de código. O pacote inclui a pasta `docs/` (com este manual e a documentação de arquitetura), orientações rápidas (`LEIA-ME-executavel.txt`) e os scripts na pasta `tampermonkey/`.

### Executar pelo código-fonte

No PowerShell, na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe app_noc.py
```

O aplicativo prepara o `.env` automaticamente a partir do exemplo e acrescenta opções ausentes a configurações existentes sem apagar suas chaves. Alterações no `.env` entram em vigor após reiniciar o aplicativo.

### Instalar a extensão do Edge

1. No aplicativo, abra o menu **⋯ > Instalar extensão do Edge**.
2. Clique em **Copiar caminho** e depois em **Abrir extensões** (ou acesse `edge://extensions/` no Microsoft Edge).
3. Ative a chave **Modo do desenvolvedor**.
4. Clique em **Carregar sem compactação**.
5. Selecione a pasta cujo caminho foi copiado no passo 2.
6. Confira o cartão **NOCFlow — Zabbix e Movidesk** (versão 2.2.3) e mantenha a extensão habilitada.
7. Recarregue as páginas abertas do Zabbix e do Movidesk com **F5**.

Instale a extensão no mesmo perfil do Edge em que você já utiliza o Zabbix, o Movidesk e o WhatsApp Web. No executável, a pasta preparada fica em `%LOCALAPPDATA%\NOCFlow\edge_extension`; pelo código-fonte, em `.noc_data/edge_extension` (ou `edge_extension/` na raiz). As origens customizadas do Zabbix são preservadas em `.noc_data/extensao.json` durante atualizações.

### Atualizar uma instalação

1. Feche o NOCFlow normalmente, aguardando a confirmação **✓ Salvo**.
2. Substitua a pasta distribuída pela nova versão completa.
3. Abra o aplicativo para atualizar automaticamente os arquivos locais da extensão (preservando seus domínios Zabbix configurados).
4. Em `edge://extensions/`, clique em **Recarregar** no cartão da extensão.
5. Atualize as páginas dos sistemas com **F5** e clique em **Conectar / Reconectar** na faixa Zabbix do aplicativo.

---

## Conhecer a interface

| Área | Uso |
|---|---|
| Seletor no topo | Alternar rapidamente entre os incidentes da fila. |
| **Fila / Voltar** | Abrir ou recolher a lista completa com busca textual, filtros por severidade/ticket/etapa e contadores. |
| **+ Novo** | Criar um novo atendimento vazio preservando os anteriores. |
| Faixa **Zabbix** | Acompanhar o estado da conexão, o horário de expiração, o botão **Conectar / Reconectar** e o botão **Central operacional** (que destaca quantas rotinas/ações estão vencidas). |
| Menu **⋯** | Ações de conexão, captura/OCR, IA, instalação da extensão, configurações, consumo de tokens e gestão da fila. |
| Aba **Incidente** | Importar dados do Zabbix, ler print com OCR e revisar alerta, servidor, severidade, dados operacionais, horário e link. |
| Campo **Ticket** | Receber automaticamente ou digitar o número do chamado (na barra inferior). |
| Botão de ação do ticket | Adapta-se ao contexto: **Criar ticket**, **Voltar ao formulário**, **Abrir ticket #…** ou **Informar ticket**. |
| Aba **Comunicar** | Escolher canal (`WhatsApp`, `Teams`, `E-mail`) e modelo de comunicado, informar equipe/time ou atualização, revisar/ampliar a prévia e copiar mensagem ou assunto. |
| Aba **Evidências** | Adicionar, ampliar com zoom, recortar (`Host`, `Trigger`, `Severity`) e copiar a imagem; escolher entre **Print completo** ou **Recorte** para envio ao ticket. |
| **Pendências / Atendimento** | Consultar próxima ação recomendada, avisos de coleta, status de preenchimento de cada campo do Movidesk e resolver divergências entre edições manuais e recapturas. |
| **Próximo** | Avançar automaticamente para o próximo incidente que aguarda abertura de ticket ou primeira comunicação. |
| Rodapé | Acompanhar o progresso da operação ativa, tempo decorrido e confirmação de salvamento (`✓ Salvo`). Em caso de falha, o botão **Detalhes** exibe o diagnóstico completo. |

### Atalhos de teclado

| Atalho | Ação |
|---|---|
| **Ctrl+N** | Criar novo incidente. |
| **Ctrl+I** | Importar dados JSON do Zabbix a partir do clipboard. |
| **Ctrl+Shift+V** | Ler a imagem atual do clipboard com OCR. |
| **Win+Shift+S** | Abrir a ferramenta de captura de tela do Windows. |

---

## Atendimento de ponta a ponta

1. Abra o NOCFlow e clique em **Conectar** na faixa superior Zabbix (uma vez a cada sessão de até 12 horas).
2. Na página do evento ou lista de problemas do Zabbix, expanda o painel **NOCFlow — Zabbix e Movidesk** e clique em **Enviar ao NOCFlow**.
3. Na aba **Incidente**, confira os dados preenchidos automaticamente. Se o incidente usar regras específicas de cliente, consulte a **Central operacional** para avaliar o perfil.
4. Confira a aba **Evidências** (a extensão já anexa a imagem renderizada de *Host / Trigger / Severity* quando enviada da página do evento).
5. Clique em **Criar ticket**. O Edge abrirá o formulário do Movidesk e preencherá automaticamente título, link + print, tipo/ação interna, categoria, urgência, solicitante/serviço (quando presentes nas tags) e apontamento de horas (`00:03` / `Observability`).
6. Revise os campos no Movidesk e clique em **Salvar**. O número do protocolo voltará sozinho para o incidente correspondente no NOCFlow.
7. Na aba **Comunicar**, selecione o canal e o modelo desejado, preencha o acionamento/time responsável se aplicável e copie o comunicado.
8. Clique em **Próximo** para avançar ao próximo item pendente ou arquive o atendimento concluído.

---

## Importar alertas do Zabbix

### Envio direto pela extensão

1. No aplicativo, clique em **Conectar** (ou **⋯ > Conectar Zabbix**).
2. A guia local aberta no Edge confirmará a conexão e poderá ser fechada.
3. Abra o detalhe de um evento Zabbix (`tr_events.php` com `eventid` na URL).
4. Expanda **NOCFlow — Zabbix e Movidesk** e clique em **Enviar ao NOCFlow**.
5. O incidente entra imediatamente na fila. Se você já estiver editando outro item, o aplicativo preserva sua edição atual e exibe um aviso **recebido(s) · Ver** para alternar quando quiser.

Além de *Host*, *Trigger/Event name*, *Severity*, *Operational data*, *Time*, *URL* e `eventid`, o coletor extrai automaticamente as **tags do evento** (como `Movidesk` para o solicitante e a tag de serviço/tecnologia) e a imagem renderizada das linhas principais.

### Importação em lote (até 100 eventos)

1. Na lista de problemas do Zabbix (`zabbix.php?action=problem.view`), marque os eventos desejados ou utilize o botão **Selecionar primeiras N linhas** no painel da extensão.
2. Clique em **Enviar selecionados ao NOCFlow** (ou **Copiar selecionados para NOCFlow** seguido de **Ctrl+I** no app).
3. O coletor aproveita os dados visíveis na tabela e busca em segundo plano (até 2 requisições simultâneas com timeout de 8s) os detalhes e tags faltantes de cada evento.

### Alternativa pelo clipboard / Tampermonkey

Caso utilize os scripts da pasta `tampermonkey/` (`NOCFlow-Zabbix.user.js` e `NOCFlow-Movidesk.user.js`), clique em **Copiar dados para NOCFlow** no navegador e pressione **Ctrl+I** (ou clique em **Importar dados**) no aplicativo. Mantenha apenas uma implementação ativa por página (extensão ou Tampermonkey) para evitar botões duplicados.

---

## Organizar a fila

- **Visão de Fila:** clique em **Fila** para pesquisar por texto livre ou filtrar por severidade, presença de ticket e etapa (**Recebido**, **Em revisão**, **Aguardando ticket**, **Pronto para comunicar**, **Arquivado**).
- **Deduplicação inteligente por `(instância, eventid)`:** reimportar o mesmo evento atualiza dados novos sem apagar o ticket já vinculado nem sobrescrever campos que você editou manualmente. Quando um valor novo diverge da sua edição manual, um aviso aparece em **Pendências** permitindo escolher entre **Aplicar valor selecionado** ou **Manter minha revisão**.
- **Proteção contra remoções acidentais:** **⋯ > Desfazer remoção** restaura até os últimos 20 incidentes removidos na sessão atual.

---

## Capturar imagens e usar OCR

| Ação | Quando usar |
|---|---|
| **Ler print** (`Ctrl+Shift+V`) | Lê a imagem copiada no clipboard (`Win+Shift+S`) e preenche os campos via OCR local do Windows. |
| **Evidências > Adicionar print** | Apenas anexa a imagem do clipboard ao incidente atual sem alterar os campos de texto. |
| **⋯ > Reler print guardado** | Reexecuta o OCR local sobre a imagem já anexada ao incidente. |
| **⋯ > Completar com IA** | Consulta Groq (texto do OCR) e/ou Gemini (visão) sob demanda apenas para preencher os campos que ficaram em branco. |

---

## Preencher o Movidesk

Ao clicar em **Criar ticket**, a extensão automatiza o preenchimento no Movidesk:

1. **Título (Assunto):** `{alerta} - {servidor}`.
2. **Descrição (Corpo da ação):** insere o link clicável do Zabbix e, logo abaixo dele, a imagem PNG da evidência (ou resumo estruturado em texto caso não haja imagem), preservando integralmente o texto prévio e a assinatura do analista no editor (Froala, TinyMCE, Kendo ou iframe).
3. **Tipo do ticket e da ação:** seleciona automaticamente **Interno** (independentemente do valor numérico interno do rádio/botão na instância).
4. **Categoria e Urgência:** seleciona a categoria (`Alerta`) e mapeia a severidade do Zabbix para a urgência correspondente (`Disaster/Crítica` → `1`, `High/Alta` → `2`, `Average/Média` → `3`, `Warning/Information/Baixa` → `4`), suportando campos nativos, Select2 (AJAX) e Kendo UI.
5. **Solicitante e Serviço pelas Tags:** quando o evento do Zabbix possui tags de identificação (ex.: `Movidesk` para cliente/solicitante e tag de serviço/tecnologia como `DBA SQL`), a extensão pesquisa nos endpoints do Movidesk e preenche automaticamente os campos **Solicitante** e **Serviço**.
6. **Apontamento de Horas e Atividade:** preenche automaticamente **Tempo apontado** com `00:03` (preservando o campo *Tempo contabilizado* intacto e abrindo a seção de horas caso esteja recolhida) e seleciona a atividade **Observability**.

Em **Pendências / Atendimento**, você confere o status individual de cada um dos 9 itens (`título`, `descrição`, `tipo/ação interna`, `categoria`, `urgência`, `tempo apontado`, `atividade`, `solicitante` e `serviço`) como **preenchido**, **pendente** ou **não localizado**.

### Retorno automático do número do ticket

Assim que você clica em **Salvar** no Movidesk, a extensão detecta o número gerado (seja pela mudança de URL para `/Ticket/Edit/{id}` ou pelo modal de protocolo `.protocol-modal`) e devolve o número e o link definitivo diretamente para o incidente de origem no NOCFlow — mesmo que você já tenha mudado para outro item da fila.

---

## Preparar comunicados e recortes

### Canais e Modelos

Na aba **Comunicar**, selecione o canal (**WhatsApp**, **Teams** ou **E-mail**) e escolha o modelo adequado ao momento do atendimento:

| Modelo | Finalidade |
|---|---|
| **Abertura normal** | Comunicação padrão de abertura com dados do alerta, servidor e ticket (sem saudação de horário). |
| **Abertura inicial** | Comunicação de abertura incluindo saudação automática (*Bom dia* / *Boa tarde* / *Boa noite*) no WhatsApp. |
| **Acionamento inicial** | Permite comunicar um acionamento mesmo antes do número do ticket quando autorizado pela regra do perfil operacional (`comunicar_sem_ticket`). |
| **Acionamento** | Registro de escalonamento para equipe/plantonista (exige informar **Acionamento** ou **Time responsável**). |
| **Atualização** | Informa andamento ou posicionamento técnico sobre um atendimento em curso (exige preencher o campo de descrição da atualização). |
| **Normalização** | Comunica o encerramento/estabilização do incidente (exige descrever a normalização). |

### Recortar evidência (`Host`, `Trigger` e `Severity`)

Na aba **Evidências**, clique em **Recortar print** para abrir o editor com zoom:
1. Selecione com o mouse as caixas correspondentes a **Host**, **Trigger** e **Severity**.
2. Clique em **Salvar recortes**.
3. Em **Imagem no ticket**, escolha se o Movidesk deve receber o **Print completo** ou o **Recorte** empilhado. Você também pode clicar em **Copiar recorte** para colar a montagem diretamente no corpo do e-mail ou conversa.

---

## Central Operacional (Regras, Agenda, Conhecimento e Relatórios)

Clique no botão **Central operacional** na faixa superior do NOCFlow para abrir a janela dedicada de gestão do turno, organizada em 5 abas:

### 1. Atendimento e Linha do Tempo
- Classifique a **Origem** (`Zabbix`, `Grafana`, `Teams`, `WhatsApp`, `E-mail`, `Telefone`, `Manual`, `Dynatrace`, `Jira`), a **Natureza** (`Incidente`, `Solicitação`, `Encaminhamento`, `Mudança`, `Rotina`), o **Perfil operacional**, o **Serviço**, a **Prioridade** e o **Relato original**.
- **Linha do tempo:** registre cada interação do atendimento (*Acionamento*, *Tentativa de contato*, *Resposta recebida*, *Escalonamento*, *Atualização*, *Observação*) com horário e autor.
- **Acompanhamento (Follow-up):** agende a próxima ação com prazo (em minutos ou horário ISO) e conclua o acompanhamento quando resolvido. Atendimentos com prazo vencido destacam um alerta no botão da Central na janela principal.
- **Referências externas:** vincule números de chamados secundários, links de mudanças ou identificadores externos.

### 2. Regras Operacionais e Perfis
- Carregue um arquivo JSON de perfis operacionais (**Carregar perfis**) ou gere um modelo base (**Salvar exemplo**).
- Clique em **Avaliar regra** para que o motor determinístico analise o incidente atual considerando **calendário, fuso horário, feriados, janelas de turno, severidade e serviço**.
- O resultado informa: prioridade recomendada, política de ticket (`criar` novo ou `vincular` a existente), permissão de comunicar sem ticket, prazos de primeiro acionamento/atualização e eventuais conflitos entre regras, permitindo clicar em **Aplicar ao atendimento**.

### 3. Agenda Operacional e Rotinas de Turno
- Cadastre checklists e tarefas periódicas do turno (**Nova rotina**) com frequência **diária**, **dias úteis**, **semanal** ou por **intervalo em minutos**, respeitando o fuso horário configurado.
- Quando uma rotina atinge o horário previsto, o botão na tela principal muda para **`Central · N vencida(s)`**.
- Selecione a rotina e clique em **Registrar execução** para documentar o resultado (`ok`, `alerta` ou `falha`), a evidência observada e o operador responsável, avançando automaticamente o próximo agendamento.

### 4. Base de Conhecimento Local e Consulta com IA
- Selecione uma pasta local contendo um arquivo `indice.json` e documentos de procedimentos em Markdown (**Selecionar base** ou **Salvar índice exemplo**).
- Clique em **Buscar procedimentos** para localizar instantaneamente os trechos validados aplicáveis ao perfil e serviço do atendimento atual.
- Opcionalmente, use **Responder com IA** ou **Revisar lacunas com IA**: a IA recebe exclusivamente os trechos locais encontrados na busca e responde citando obrigatoriamente os identificadores `[id]` das fontes.

### 5. Relatórios, Recorrência, Passagem de Turno e Exportação (CSV / PDF)
- **Diário de bordo:** consolida todos os eventos registrados na fila e na agenda dentro do período informado.
- **Passagem de turno:** gera o resumo estruturado de chamados em andamento, acompanhamentos pendentes, rotinas vencidas e ocorrências do plantão, permitindo registrar formalmente a passagem com nome do responsável e observações.
- **Indicadores:** exibe métricas reproduzíveis em JSON (volumes por etapa, severidade, origem, cumprimentos de prazo e execuções de rotina).
- **Auditoria de recorrência:** analisa toda a fila de forma determinística para identificar hosts e alertas repetidos, contabilizando ocorrências, tickets distintos abertos, itens sem ticket e aberturas em lote.
- **Exportação:** copie o texto, exporte os atendimentos para planilha (**Exportar CSV**) ou gere um documento formatado e paginado (**Exportar PDF**).

### Assistente de IA para Relatos (Sob Demanda)
- Na aba de atendimento da Central, preencha um relato livre (por exemplo, uma mensagem recebida no Teams ou WhatsApp) e clique em **Organizar relato com IA**.
- O assistente sugere o preenchimento estruturado dos campos em uma janela de revisão com caixas de seleção (*checkboxes*), permitindo escolher exatamente quais sugestões aplicar sem sobrescrever nada sem sua confirmação.

---

## Utilitários do navegador e WhatsApp Web

### Painel no Zabbix (`NOCFlow — Zabbix e Movidesk`)

- **Ações principais em destaque:**
  - **Enviar ao NOCFlow** (na página do evento) / **Enviar selecionados ao NOCFlow** (na lista de problemas).
  - **Copiar link + imagem**: copia link clicável + tabela renderizada (*Host / Trigger / Severity*) pronta para colar em editores ricos.
- **Mais opções:**
  - **Copiar Trigger - Host**, **Copiar chamado reconhecido** e **Copiar imagem Host / Trigger / Severity**.

### Painel no Movidesk (`NOCFlow — Zabbix e Movidesk`)

- **Copiar número:** copia apenas o protocolo do ticket salvo.
- **Copiar ticket + assunto:** copia `{número} - {assunto}`.
- **Copiar template:** botão em destaque que copia número, assunto e link definitivo em linhas separadas.

### Assinatura no WhatsApp Web (Popup da Extensão)

1. Com o **WhatsApp Web** aberto em uma conversa, clique no ícone da extensão **NOCFlow** na barra de ferramentas do Microsoft Edge.
2. Digite seu nome (ex.: `João Vitor`) — ele fica salvo no navegador para os próximos usos.
3. Clique em **Assinar mensagem**.
4. A extensão insere o cabeçalho **`*João Vitor - Equipe NOC*`** no topo da mensagem que você está digitando na caixa de texto do WhatsApp Web, **preservando formatações existentes (negrito, quebras de linha)**, **sem duplicar** caso já esteja assinada e **sem enviar a mensagem automaticamente**.

---

## Configurar o aplicativo e a IA

Abra **⋯ > Configurações** no aplicativo (ou execute `Abrir configuracoes.cmd` na pasta distribuída) para editar o arquivo `.env`:

| Variável | Padrão | Finalidade |
|---|---|---|
| `NOME_OPERADOR` | vazio | Nome exibido antes de `Equipe NOC` nos comunicados de WhatsApp e nos registros da Central Operacional. |
| `MOVIDESK_URL` | `https://empresa.movidesk.com` | URL base da instância do Movidesk da sua organização. |
| `MOVIDESK_LOGIN_TIMEOUT_SECONDS` | `120` | Tempo máximo (5–300s) aguardando login/abertura do formulário no Edge. |
| `MOVIDESK_RETORNO_TIMEOUT_SECONDS` | `28800` | Tempo máximo (60–86400s, padrão 8h) aguardando o salvamento e retorno do número do ticket. |
| `OCR_TIMEOUT_SECONDS` | `15` | Tempo limite (5–300s) para leitura local de imagem via Windows OCR. |
| `IA_AUTOMATICA` | `false` | Se `true`, o botão **Ler print** passa a complementar automaticamente campos faltantes usando IA. |
| `GROQ_API_KEY` | vazio | Chave opcional da API Groq para extração de texto e assistente da Central Operacional. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Modelo textual utilizado na Groq. |
| `GROQ_FALLBACK_ENABLED` | `true` | Habilita o uso da Groq quando a chave estiver configurada. |
| `GROQ_TIMEOUT_SECONDS` | `30` | Timeout (5–300s) por chamada à Groq. |
| `GROQ_MAX_COMPLETION_TOKENS` | `2048` | Limite de tokens de saída (128–32768) na Groq. |
| `GEMINI_API_KEY` | vazio | Chave opcional da API Google Gemini para leitura visual complementar de prints. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Modelo multimodal configurado para o Gemini. |
| `GEMINI_TIMEOUT_SECONDS` | `60` | Timeout (5–300s) por chamada ao Gemini. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Limite de tokens de saída (128–32768) no Gemini. |

---

## Acompanhar consumo e desempenho

Em **⋯ > Consumo e detalhes**, o operador acompanha:
- Tokens de entrada, saída e total reportados por cada provedor (Groq e Gemini) na sessão atual.
- Limites e cotas restantes informados pelos cabeçalhos da última resposta da Groq.
- Proporção de incidentes resolvidos com operação 100% local versus chamadas de IA.
- Tempo de processamento e origem da coleta de cada item da fila.

---

## Dados, backup e encerramento

| Conteúdo | Executável Windows (`NOCFlow.exe`) | Execução pelo Código-Fonte (`app_noc.py`) |
|---|---|---|
| Configurações (`.env`) | `%LOCALAPPDATA%\NOCFlow\.env` | `.env` na raiz do repositório |
| Fila, imagens, agenda e histórico | `%LOCALAPPDATA%\NOCFlow\.noc_data\rascunho.json` | `.noc_data/rascunho.json` |
| Domínios Zabbix da extensão | `%LOCALAPPDATA%\NOCFlow\.noc_data\extensao.json` | `.noc_data/extensao.json` |
| Logs rotativos da aplicação | `%LOCALAPPDATA%\NOCFlow\.noc_data\noc.log` | `.noc_data/noc.log` |
| Pasta da extensão para o Edge | `%LOCALAPPDATA%\NOCFlow\edge_extension` | `.noc_data/edge_extension` (ou `edge_extension/`) |

Para fazer backup completo da sua operação local, feche o aplicativo aguardando **✓ Salvo** e copie o arquivo `.env` e a pasta `.noc_data/`.

---

## Solução de problemas

| Situação | Como resolver |
|---|---|
| **"Origem Zabbix não configurada."** | Verifique se a URL do seu Zabbix consta em `.noc_data/extensao.json` (ou no `manifest.json`), recarregue a extensão em `edge://extensions/` e aperte **F5** na aba do Zabbix. |
| **Painel não aparece no Zabbix ou Movidesk** | Confirme que a extensão está ativa em `edge://extensions/`, recarregue-a e pressione **F5** na página. Na página de evento Zabbix, a URL deve conter `tr_events.php` ou `action=problem.view`. |
| **Envio do Zabbix pede conexão** | No NOCFlow, clique em **Conectar** (ou **Reconectar**) na faixa Zabbix e aguarde a confirmação na guia aberta. |
| **Movidesk abre mas não preenche** | Confira se você já está logado no Movidesk naquele perfil do Edge e se a extensão está instalada no mesmo perfil. |
| **Solicitante ou Serviço não preencheu no ticket** | O preenchimento automático desses dois campos depende da existência das tags de solicitante (`Movidesk`) e de serviço/tecnologia no evento do Zabbix e de correspondência única na busca do Movidesk; caso não haja tag, selecione-os manualmente. |
| **Número do ticket não retornou sozinho** | Mantenha a guia até aparecer o número na URL ou no modal de protocolo; se a guia foi fechada antes, digite o número no campo **Ticket**. |
| **Assinatura no WhatsApp Web informa erro** | Certifique-se de estar com uma conversa aberta no `https://web.whatsapp.com` e com um texto já iniciado na caixa de mensagem do rodapé antes de clicar em **Assinar mensagem**. |
| **Nenhuma imagem no clipboard ao clicar em Ler print** | Faça uma nova captura com **Win+Shift+S** (copiar um arquivo `.png` pelo Windows Explorer não copia os pixels para a área de transferência). |
| **Porta 18764 ocupada** | Feche outra instância aberta do NOCFlow no Gerenciador de Tarefas e tente novamente. |
