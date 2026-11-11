# Manual de uso — NOCFlow

Este manual acompanha o operador desde a instalação até a comunicação de um incidente. A extensão e os painéis do navegador utilizam o nome **NOCFlow — Zabbix e Movidesk**.

Versão dos recursos de fluxo e interface: **2.1.0**.

Consulte também a [apresentação do projeto](README.md) e a [arquitetura técnica](docs/arquitetura.md).

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
- [Utilitários do navegador](#utilitários-do-navegador)
- [Configurar o aplicativo e a IA](#configurar-o-aplicativo-e-a-ia)
- [Acompanhar consumo e desempenho](#acompanhar-consumo-e-desempenho)
- [Dados, backup e encerramento](#dados-backup-e-encerramento)
- [Solução de problemas](#solução-de-problemas)

## Requisitos

- Windows 10 ou 11.
- Microsoft Edge, com acesso e login nas instâncias utilizadas de Zabbix e Movidesk.
- Português ou Inglês instalado no Windows para a leitura de imagens por OCR.
- Python 3.10+ apenas para executar pelo código-fonte ou gerar o executável.

O fluxo principal funciona sem chaves de IA. O acesso aos sites depende da rede da organização; processamento de capturas, fila e templates é local. A complementação por IA exige conexão com o provedor configurado.

## Instalação e atualização

### Usar o executável Windows

1. Copie a pasta `NOCFlow` completa para o computador.
2. Mantenha `NOCFlow.exe` e a pasta `_internal` no mesmo diretório.
3. Abra `NOCFlow.exe` ou o atalho **NOCFlow**, se houver.
4. Aguarde a recuperação do rascunho e a mensagem de prontidão.

O computador que recebe o pacote não precisa de Python nem de VS Code. O pacote inclui este `manual.md`, orientações rápidas e os userscripts Tampermonkey.

### Executar pelo código-fonte

No PowerShell, na raiz do repositório:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app_noc.py
```

O aplicativo prepara o `.env` a partir do exemplo e acrescenta opções ausentes a configurações existentes. Preserve seu arquivo ao atualizar. Alterações de configuração são aplicadas após reiniciar o aplicativo.

### Instalar a extensão do Edge

1. No aplicativo, abra **⋯ > Instalar extensão do Edge**.
2. Use **Abrir extensões**, ou acesse `edge://extensions/` no Edge.
3. Ative **Modo do desenvolvedor**.
4. Clique em **Carregar sem compactação**.
5. Selecione a pasta indicada pelo aplicativo. O botão **Copiar caminho** ajuda a localizá-la.
6. Confira o cartão **NOCFlow — Zabbix e Movidesk** e mantenha a extensão habilitada.
7. Recarregue as páginas do Zabbix e do Movidesk com **F5**.

Instale a extensão no perfil do Edge em que você utiliza os sistemas. Com o executável, a pasta normalmente é `%LOCALAPPDATA%\NOCFlow\edge_extension`; pelo código-fonte, é `edge_extension` na raiz do projeto.

Domínios incluídos na configuração distribuída:

- `https://zabbix.example.com` (substitua pela sua instância)
- `https://zabbix-secondary.example.com` (substitua pela sua instância secundária)
- `https://*.movidesk.com`

A configuração de outros domínios está descrita na documentação de arquitetura, na seção **Adaptação e manutenção**.

### Atualizar uma instalação

1. Feche o NOCFlow normalmente, aguardando o salvamento.
2. Substitua a pasta distribuída pela nova versão completa.
3. Abra o aplicativo para atualizar os arquivos locais da extensão.
4. Em `edge://extensions/`, clique em **Recarregar** no cartão da extensão.
5. Atualize as páginas dos sistemas e conecte novamente o Zabbix pelo aplicativo.

Configuração e fila do executável ficam fora da pasta distribuída, em `%LOCALAPPDATA%\NOCFlow`.

## Conhecer a interface

| Área | Uso |
|---|---|
| Seletor no topo | Alternar entre os incidentes da fila. |
| **Fila / Voltar** | Abrir ou recolher a lista com busca, filtros, etapas e contadores. Selecionar outro item retorna ao editor. |
| **+ Novo** | Acrescentar um incidente vazio. |
| Faixa **Zabbix** | Ver a conexão, seu prazo e a ação **Conectar / Reconectar**. O aviso de recebidos permite abrir os eventos que chegaram durante uma edição. |
| Menu **⋯** | Conexão, imagens, IA, instalação da extensão, configurações, consumo e ações da fila. |
| Aba **Incidente** | Importar dados, ler um print e revisar alerta, servidor, severidade, dados operacionais, horário e link. |
| Campo **Ticket** | Receber ou digitar o número do chamado. Fica na barra inferior. |
| Ação do ticket | **Criar ticket**, **Voltar ao formulário**, **Abrir ticket #…** ou **Informar ticket**, conforme o atendimento. |
| Aba **Comunicar** | Escolher canal e modelo, revisar a prévia com rolagem, ampliá-la e copiar a mensagem ou assunto. |
| Aba **Evidências** | Adicionar, ampliar, recortar e copiar a imagem; escolher explicitamente qual imagem vai para o ticket. |
| Orientação e **Pendências / Atendimento** | Ver a próxima ação, avisos de coleta, resultados por campo e diferenças em relação às revisões. |
| **Próximo** | Avançar ao próximo incidente que precisa de ticket ou primeira comunicação. |
| Rodapé | Acompanhar operação, tempo decorrido e salvamento. Em falhas, **Detalhes** abre a mensagem completa. |

Atalhos:

| Atalho | Ação |
|---|---|
| **Ctrl+N** | Novo incidente. |
| **Ctrl+I** | Importar dados JSON do clipboard. |
| **Ctrl+Shift+V** | Ler a imagem atual do clipboard. |
| **Win+Shift+S** | Abrir a captura de tela do Windows. |

Durante operações demoradas, algumas ações ficam desabilitadas. Aguarde a conclusão indicada no rodapé.

## Atendimento de ponta a ponta

1. Abra o NOCFlow e clique em **Conectar**, na faixa Zabbix.
2. No evento do Zabbix, expanda o painel **NOCFlow — Zabbix e Movidesk** e clique em **Enviar ao NOCFlow**.
3. Na aba **Incidente**, confira os dados importados e complete o que faltar.
4. Confira a aba **Evidências**. Para anexar uma captura sem interpretar seus campos, use **Adicionar print** após **Win+Shift+S**.
5. Clique em **Criar ticket**, revise o formulário e complete os campos exigidos pelo site.
6. Salve o ticket manualmente. Aguarde o número aparecer no incidente original.
7. Na aba **Comunicar**, escolha canal e modelo, informe acionamento ou time quando necessário e copie o comunicado.
8. Use **Próximo** para continuar a fila. Arquive o atendimento quando terminar a operação local.

## Importar alertas do Zabbix

### Envio direto pela extensão

1. No aplicativo, escolha **⋯ > Conectar Zabbix**.
2. Aguarde a confirmação na guia local aberta pelo Edge. Essa guia pode ser fechada após confirmar a conexão.
3. Abra o detalhe de um evento Zabbix com `eventid` na URL.
4. Expanda **NOCFlow — Zabbix e Movidesk** e clique em **Enviar ao NOCFlow**.
5. Volte ao aplicativo e revise o incidente. Se já estava editando outro, clique no aviso **recebido(s) · Ver** para abrir os recém-chegados.

A coleta utiliza os campos disponíveis na página: Host, Trigger/Event name, Severity, Operational data e Time, além do link e do identificador do evento. No detalhe de um evento, a extensão também tenta incluir a imagem das linhas Host, Trigger e Severity.

A conexão de importação dura até **12 horas** na sessão atual. Reconecte após reiniciar o aplicativo ou o navegador. O preenchimento do Movidesk estabelece seu próprio vínculo por pedido.

A faixa de conexão indica **conectado**, **desconectado**, **conexão expirada** ou **sem resposta do navegador**. A extensão envia um sinal local por minuto; a ausência por cerca de 2,5 minutos muda o indicador. Use **Reconectar** para recuperar o envio.

### Importação pelo clipboard

1. No evento, abra **Mais opções > Copiar dados para NOCFlow**. No userscript, o botão fica em destaque no painel principal.
2. No aplicativo, clique em **Importar dados** ou use **Ctrl+I**.
3. Revise o resultado.

Esse botão copia JSON estruturado. A cópia apenas do link, do título ou de um texto de e-mail não contém o contrato necessário para importar o evento.

### Vários eventos de uma vez

1. Abra a lista de problemas do Zabbix, em `zabbix.php?action=problem.view`.
2. Marque as linhas desejadas, ou use **Selecionar primeiras N linhas**.
3. Clique em **Enviar selecionados ao NOCFlow**, ou em **Copiar selecionados para NOCFlow** e depois importe no aplicativo.
4. Use o seletor da fila para revisar os eventos individualmente.

O limite é de **100 eventos por importação** e **2 MB por envio/clipboard**. Linhas anteriormente marcadas continuam selecionadas. Os dados já disponíveis na lista são aproveitados; detalhes faltantes são buscados com até duas requisições simultâneas, com limite de 8 segundos por requisição. Eventos parciais continuam disponíveis para revisão.

### Usar Tampermonkey

Instale os scripts da pasta `tampermonkey`:

- `NOCFlow-Zabbix.user.js`: coleta de dados, seleção em lote e utilitários de imagem.
- `NOCFlow-Movidesk.user.js`: cópia de número, link, assunto e texto de e-mail.

No Zabbix, use **Copiar dados para NOCFlow** e depois **Importar dados** no aplicativo. O envio direto e o preenchimento/retorno do Movidesk são funções da extensão Edge.

Use uma única implementação dos utilitários em cada página: extensão ou userscript. Desative scripts antigos equivalentes para evitar controles duplicados. Para atualizar o userscript, reinstale o arquivo gerado da versão recebida e recarregue a página.

## Organizar a fila

- Cada item mantém seus próprios campos, ticket, metadados e imagem.
- **Fila** abre uma visão com busca por texto e filtros de severidade, presença de ticket e etapa. Os contadores resumem os ativos, os que aguardam ticket e os prontos para comunicar. **Voltar** recolhe a lista.
- Etapas: **Recebido**, **Em revisão**, **Aguardando ticket**, **Pronto para comunicar** e **Arquivado**. São indicadores do trabalho local; não alteram o status do ticket no Movidesk.
- **Próximo** procura itens sem ticket ou sem primeira cópia de comunicado, pulando arquivados e formulários que aguardam retorno.
- **Arquivar / Reabrir**, na fila ou no menu **⋯**, preserva o atendimento. Para encontrá-lo depois, filtre por **Arquivado** ou **Todos**.
- **+ Novo** acrescenta um item sem apagar os anteriores.
- **⋯ > Desfazer novo incidente** retorna ao item anterior. Um novo item ainda vazio é removido nessa ação.
- **⋯ > Remover incidente da fila** remove o item local selecionado. Tickets e eventos nos sites não são excluídos por essa ação.
- **⋯ > Desfazer remoção** recupera até as últimas 20 remoções da sessão, incluindo retornos de ticket recebidos enquanto o item estava removido. Essa possibilidade termina ao fechar o aplicativo.
- Uma nova importação da mesma instância Zabbix e do mesmo `eventid` atualiza o incidente existente. Campos corrigidos manualmente são protegidos. Abra **Pendências** para comparar os valores e escolher **Aplicar valor selecionado** ou **Manter minha revisão**, campo a campo.
- Campos vazios recebidos não apagam dados anteriores; ticket e encaminhamento são preservados. Avisos de coleta ficam disponíveis em **Pendências**.
- Envios da extensão mantêm o incidente em edição e seu cursor. A importação manual pelo clipboard seleciona o primeiro item importado; um formulário inicialmente vazio também pode receber o primeiro evento diretamente.
- Se a importação incluir outra imagem, ela atualiza a evidência e limpa os recortes da imagem anterior. Caso contrário, a imagem já guardada é mantida.
- Um novo `eventid` ou outra instância gera outro incidente, mesmo que alerta e servidor sejam iguais.

A fila é salva automaticamente. Confira **✓ Salvo** no rodapé antes de encerrar uma etapa importante.

## Capturar imagens e usar OCR

### Escolher a ação adequada

| Ação | Resultado |
|---|---|
| **Ler print** | Lê a imagem atual do clipboard e interpreta os campos com OCR. |
| **Evidências > Adicionar print** ou **⋯ > Guardar print sem extrair** | Guarda a imagem atual do clipboard como evidência, sem extrair os campos. |
| **⋯ > Reler print guardado** | Executa OCR novamente na imagem já guardada, sem IA. |
| **⋯ > Completar com IA** | Usa a imagem guardada para tentar completar campos pendentes; se não houver imagem, tenta o clipboard. |
| **Evidências > Copiar print** ou **⋯ > Copiar print** | Copia a imagem guardada para colar em outro aplicativo. |

### Ler uma captura

1. Para um evento diferente, prefira **+ Novo** antes da captura.
2. Use **Win+Shift+S** e selecione a região que contém o alerta.
3. Clique em **Ler print** ou use **Ctrl+Shift+V**.
4. Aguarde o processamento local.
5. Revise alerta, servidor, severidade, dados operacionais e horário.

O OCR reconhece rótulos em Português e Inglês e considera as posições das palavras. Campos ausentes, valores conflitantes ou horários inválidos exigem revisão. Se for reconhecido outro alerta/servidor, o aplicativo cria um novo incidente e preserva a evidência do anterior.

Uma imagem não fornece identidade confiável por `eventid`. Para ocorrências repetidas do mesmo host/alerta, use **+ Novo** ou importe o evento estruturado pelo Zabbix.

Com `IA_AUTOMATICA=false`, **Ler print** usa somente OCR e regras locais. Com `true`, o botão passa a indicar **Ler print + IA**.

## Preencher o Movidesk

1. Revise **Alerta** e **Servidor**, obrigatórios para iniciar o preenchimento.
2. Confira o link Zabbix e a imagem do incidente.
3. Clique em **Criar ticket**.
4. Aguarde a nova guia; faça login se necessário.
5. Confira o preenchimento e complete os demais campos exigidos pelo site, como Solicitante e Serviço.
6. Salve o ticket manualmente.
7. Aguarde o retorno do número para o campo **Ticket** do incidente correspondente.

O preenchimento prepara:

- Título no formato `{alerta} - {servidor}`.
- Link do Zabbix e imagem embutida, quando houver evidência; sem imagem, uma descrição textual dos campos.
- Conteúdo anterior e assinatura do agente preservados abaixo do conteúdo inserido.
- Tipo/ação **INTERNO**, quando os controles correspondentes estiverem disponíveis.
- Categoria **Alerta** e urgência correspondente à severidade, conforme as opções do formulário.

Referência do mapeamento de urgência:

| Severidade reconhecida | Opção buscada no Movidesk |
|---|---|
| Disaster / Desastre / Crítica | Nível 1, Crítica ou Urgente. |
| High / Alta | Nível 2 ou Alta. |
| Average / Média / Normal | Nível 3 ou Média. |
| Warning / Aviso / Information / Não classificado | Nível 4 ou Baixa. |

Revise as escolhas quando a instância tiver categorias ou níveis personalizados. Em **Pendências / Atendimento**, o relatório indica **preenchido**, **pendente** ou **não localizado** para título, descrição, tipo/ação interna, categoria e urgência. O resultado descreve a tentativa automática, antes da revisão manual no site.

Em **Evidências > Imagem no ticket**, escolha **Print completo** ou **Recorte**. Salvar recortes não muda essa escolha automaticamente. **Recorte** exige Host, Trigger e Severity selecionados.

### Retorno do número

A extensão identifica o número em rotas como `/Ticket/Edit/123`, `/Ticket/Create/123`, `?id=123` nessas rotas ou no modal de protocolo. O retorno é associado ao incidente que originou o pedido, mesmo que outro esteja selecionado.

O prazo padrão para o formulário/login é de **120 segundos**. Após o preenchimento, o retorno pode ser aguardado por **8 horas**. Mantenha o NOCFlow e a guia do ticket abertos durante esse período.

Se o retorno não ocorrer, digite somente os números no campo **Ticket**. Um número já informado e diferente do retornado exige revisão; ele não é substituído silenciosamente. Se o incidente tiver sido removido da fila, o retorno não o recria.

### Continuar ou recuperar um atendimento

- Com número válido informado, **Abrir ticket #…** abre o link definitivo do chamado.
- Com formulário aguardando salvamento, **Voltar ao formulário** localiza a guia existente, sem repetir o preenchimento.
- Após falha, fechamento da guia, expiração ou reinício do aplicativo, **Informar ticket** orienta o preenchimento manual do número salvo.
- Se for necessário outro formulário, confira a guia anterior e use **Pendências > Preparar novo formulário**. Essa ação substitui o vínculo local anterior.
- Um número retornado diferente do informado fica registrado. Em **Pendências**, escolha **Usar ticket retornado** ou **Manter ticket informado** após conferir o chamado.

## Preparar comunicados e recortes

Na aba **Comunicar**, escolha o canal e confira a prévia. Alerta, servidor e ticket são obrigatórios para copiar os comunicados.

| Canal | Conteúdo e ação |
|---|---|
| **WhatsApp** | Ticket, servidor, severidade, alerta, situação e acionamento. Preencha **Acionamento** quando necessário e use **Copiar mensagem**. |
| **Teams** | Número do ticket, alerta, link do Movidesk e time responsável. Preencha **Time responsável** e use **Copiar mensagem**. |
| **E-mail** | Corpo com os dados do incidente e assunto no formato `ticket - alerta - servidor`. Use **Assunto** e **Copiar e-mail**. |

As ações copiam para o clipboard. Cole o conteúdo no canal desejado e faça o envio pelo aplicativo correspondente.

### Modelos e última cópia

| Modelo | Uso |
|---|---|
| **Abertura normal** | Padrão: dados do incidente e ticket, sem saudação de horário. |
| **Abertura inicial** | Mesmo conteúdo, com Bom dia / Boa tarde / Boa noite no WhatsApp. |

O modelo fica salvo por incidente. Novos incidentes usam **Abertura normal**; modelos antigos indisponíveis também são restaurados como abertura normal. A última cópia bem-sucedida registra horário e modelo por canal; esse registro indica **cópia**, não envio ou recebimento da mensagem. A prévia tem barra de rolagem e o botão **Ampliar prévia**, útil em janelas pequenas.

### Salvar seu nome para o WhatsApp

1. Abra **Comunicar** e selecione **WhatsApp**.
2. Preencha **Seu nome**, por exemplo `João`.
3. Clique em **Salvar nome**. A mensagem passará a começar com **João - Equipe NOC**.

O nome é salvo uma vez na configuração local e reutilizado nos próximos incidentes e após reabrir o aplicativo. Depois de salvar, aparece uma linha compacta; use **Editar nome** para alterar. Para voltar ao cabeçalho **Equipe NOC**, apague o nome e salve novamente.

### Recortar a evidência para e-mail

1. Guarde uma imagem no incidente.
2. Abra **Evidências > Recortar print**.
3. No editor, selecione **Host**, **Trigger** e **Severity**, arrastando sobre cada trecho.
4. Use o zoom e as barras de rolagem para ajustar a seleção. **Limpar seleção** permite refazer o campo atual.
5. Confira a prévia e clique em **Salvar recortes**.
6. Use **Copiar recorte** e cole no corpo do e-mail ou em outro destino que aceite imagens.

Os recortes são empilhados na ordem Host → Trigger → Severity, preservando os pixels. O print completo continua guardado. As coordenadas são salvas por incidente e restauradas ao trocar de item ou reiniciar. Substituir a imagem limpa os recortes anteriores. Clique na imagem ou em **Ampliar** para examiná-la com zoom e rolagem.

## Utilitários do navegador

### Painel no detalhe do evento Zabbix

| Botão | Uso |
|---|---|
| **Copiar dados para NOCFlow** | Copiar o JSON para importar no aplicativo. |
| **Enviar ao NOCFlow** | Enviar diretamente à fila pela extensão conectada. |
| **Copiar link** | Copiar a URL atual. |
| **Copiar Trigger - Host** | Copiar o título formado pelos campos do evento. |
| **Copiar chamado reconhecido** | Procurar o número do chamado no histórico de reconhecimentos. |
| **Copiar imagem Host / Trigger / Severity** | Renderizar e copiar as linhas correspondentes aos três campos. |
| **Copiar link + imagem** | Copiar o link clicável do evento seguido da imagem Host/Trigger/Severity para colar em editores que aceitam HTML, como o corpo do ticket ou e-mail. Em destinos de texto simples, é colado apenas o link. |
| **Copiar e-mail + imagem** | Copiar texto e HTML com a imagem para destinos que aceitam esse formato. |

Na lista de problemas, aparecem as ações de seleção e cópia/envio em lote descritas anteriormente. **Enviar** está disponível pela extensão.

As ações principais ficam em destaque: **Enviar ao NOCFlow** e **Copiar link + imagem** no evento. Cópias auxiliares ficam em **Mais opções**. Uma coleta parcial informa as pendências no painel e no aplicativo.

A imagem produzida no navegador é uma renderização do HTML. Para evidência dos pixels exatos da tela, utilize **Win+Shift+S**. A biblioteca de renderização carrega sob demanda: empacotada na extensão e obtida por CDN no userscript. O resultado pode ser reutilizado enquanto conteúdo e apresentação relevantes permanecerem iguais.

### Painel no Movidesk

| Botão | Uso |
|---|---|
| **Copiar número** | Copiar o número identificado do ticket salvo. |
| **Copiar link** | Copiar o link definitivo `/Ticket/Edit/{número}` do ticket salvo, inclusive quando o número apareceu em um modal. |
| **Copiar ticket + assunto** | Copiar o número e o título disponíveis. |
| **Copiar template** | Ação destacada que copia número, assunto e link definitivo do ticket. |

## Configurar o aplicativo e a IA

Abra **⋯ > Configurações** para editar o `.env` em uso. No pacote Windows, **Abrir configuracoes.cmd** abre a configuração em `%LOCALAPPDATA%\NOCFlow`. Salve o arquivo e reinicie o aplicativo.

### Referência das opções

| Variável | Padrão do projeto | Finalidade |
|---|---|---|
| `NOME_OPERADOR` | vazio | Nome antes de `Equipe NOC` no WhatsApp; também pode ser definido pelo botão **Salvar nome**. |
| `MOVIDESK_URL` | `https://empresa.movidesk.com` | Endereço base da instância, sem credenciais, query ou fragmento. |
| `MOVIDESK_LOGIN_TIMEOUT_SECONDS` | `120` | Espera pelo formulário/login. |
| `MOVIDESK_RETORNO_TIMEOUT_SECONDS` | `28800` | Espera pelo retorno do ticket após preencher. |
| `OCR_TIMEOUT_SECONDS` | `15` | Tempo máximo de leitura local. |
| `IA_AUTOMATICA` | `false` | Permitir complementação por IA ao usar **Ler print**. |
| `GROQ_API_KEY` | vazio | Chave opcional para extração de texto. |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Modelo de texto compatível com JSON Schema estrito e `reasoning_effort=low`. |
| `GROQ_FALLBACK_ENABLED` | `true` | Habilitar Groq quando houver chave; nome mantido por compatibilidade. |
| `GROQ_TIMEOUT_SECONDS` | `30` | Tempo máximo da chamada Groq. |
| `GROQ_MAX_COMPLETION_TOKENS` | `2048` | Teto de resposta Groq, incluindo raciocínio. |
| `GEMINI_API_KEY` | vazio | Chave opcional para visão. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Valor de exemplo existente no projeto; informe um modelo de visão disponível na sua conta. |
| `GEMINI_TIMEOUT_SECONDS` | `60` | Tempo máximo da chamada Gemini. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `2048` | Teto de resposta Gemini. |

Tempos de OCR/APIs/formulário aceitam **5–300 segundos**; retorno do ticket aceita **60–86400 segundos**. Tetos de tokens aceitam **128–32768**. Valores numéricos fora da faixa são limitados; valores não numéricos usam o padrão. Opções booleanas aceitam `true`, `1`, `sim` e `yes` para habilitar.

Variáveis de ambiente já definidas no processo têm prioridade sobre o `.env`. O modelo escolhido pode impor limites adicionais aos configurados.

### Completar uma captura com IA

1. Configure a chave do provedor desejado e um modelo disponível para a conta.
2. Reinicie o aplicativo.
3. Selecione o incidente com a imagem e revise os campos conhecidos.
4. Escolha **⋯ > Completar com IA**.
5. Revise o resultado e eventuais avisos no rodapé.

O OCR é tentado primeiro. Com texto disponível e Groq habilitada, ela recebe somente o trecho relevante do OCR. Se houver falha ou campos ainda vazios, Gemini configurado pode receber a imagem para completar as pendências. Sem texto legível, somente a visão é utilizada.

Quando os dados locais/revisados já resolvem os campos, nenhuma API é chamada. Cada provedor é consultado no máximo uma vez por extração; resultados completos podem ser reutilizados no cache da sessão. Os tempos das etapas opcionais podem se somar.

O texto enviado à Groq é limitado a 8.000 caracteres. Se exceder o limite, faça uma captura mais focada no alerta. As importações de dados do Zabbix continuam locais mesmo com IA automática habilitada.

## Acompanhar consumo e desempenho

Abra **⋯ > Consumo e detalhes** para consultar:

- Uso de tokens reportado pelos provedores na sessão.
- Cotas e tempo de renovação informados na última resposta Groq.
- Proporção de incidentes com última operação local.
- Origem, tempo da última operação, chamadas de IA e tokens reportados de cada incidente.

Gemini não fornece cota restante nessa integração. Valores ausentes são exibidos como não informados. Os tetos de resposta limitam a saída, não os tokens de entrada nem o gasto total da conta.

O painel por API é reiniciado ao fechar o aplicativo; tokens acumulados nos metadados dos incidentes são persistidos com a fila. As métricas descrevem os incidentes presentes e suas últimas operações, não todo o histórico de uso.

## Dados, backup e encerramento

| Conteúdo | Executável Windows | Execução pelo código-fonte |
|---|---|---|
| Configuração | `%LOCALAPPDATA%\NOCFlow\.env` | `.env` na raiz do projeto |
| Fila e imagens | `%LOCALAPPDATA%\NOCFlow\.noc_data\rascunho.json` | `.noc_data/rascunho.json` |
| Logs | `%LOCALAPPDATA%\NOCFlow\.noc_data\noc.log` | `.noc_data/noc.log` |
| Extensão carregada | `%LOCALAPPDATA%\NOCFlow\edge_extension` | `edge_extension/` |

Para fazer backup, feche normalmente o aplicativo e copie `.env` e `.noc_data` do diretório usado. Para restaurar, coloque os arquivos no diretório correspondente com o aplicativo fechado e reabra. Essas cópias contêm configurações e dados dos atendimentos.

O rascunho recupera a fila e o incidente ativo. Formatos antigos são migrados no próximo salvamento. Se um arquivo estiver inválido, o aplicativo tenta preservar uma cópia `rascunho-invalido-*.json` antes de novas gravações; se não conseguir, suspende o salvamento na sessão.

Ao fechar, aguarde o salvamento. Se houver falha, escolha entre continuar aberto para resolver ou fechar sem salvar. A sessão do navegador permanece no Edge. Ao reiniciar, pedidos de retorno anteriormente ativos aparecem como interrompidos: confira o ticket salvo e informe o número, ou use a recuperação em **Pendências**.

## Solução de problemas

| Situação | Como continuar |
|---|---|
| Painel não aparece | Confira a extensão, domínio e rota da página; recarregue a extensão em `edge://extensions/` e pressione F5 no site. |
| Nome ou botões antigos continuam visíveis | Abra a versão atual do NOCFlow, recarregue a extensão e a página; atualize também o userscript, se utilizado. |
| Botões duplicados | Desative scripts antigos ou o userscript equivalente quando usar os utilitários da extensão. |
| Envio pede conexão | Use **⋯ > Conectar Zabbix** e aguarde a confirmação na guia local. |
| Importação rejeita JSON | Use **Copiar dados para NOCFlow**, verifique `eventid` no link e respeite os limites de lote/tamanho. |
| Campos incompletos após importar | Confira o evento e o login; complete manualmente os campos que o layout não forneceu. |
| Nova coleta diferente da revisão | Abra **Pendências** e aplique ou rejeite cada valor recebido. |
| Incidente arquivado não aparece | Abra **Fila** e escolha **Arquivado** ou **Todos** no filtro de etapa. |
| Prévia pequena | Recolha a fila com **Voltar**, use a rolagem ou **Ampliar prévia**. |
| Nenhuma imagem no clipboard | Faça nova captura com **Win+Shift+S**. Copiar um arquivo de imagem no Explorer não equivale a copiar seus pixels. |
| Precisa usar a imagem antiga | Use **⋯ > Reler print guardado**; **Ler print** sempre lê o clipboard atual. |
| OCR não encontra texto | Capture somente o alerta com campos visíveis e confirme um idioma de OCR instalado no Windows. |
| OCR ou IA excedeu o prazo | Recorte a região relevante, revise os timeouts e consulte os detalhes da falha. |
| IA rejeitou chave/modelo ou atingiu cota | Confira a configuração e a conta do provedor; os campos locais continuam disponíveis para revisão. |
| Imagem não copia ou não aparece ao colar | Mantenha a guia em foco, confira permissões de clipboard e o suporte do destino a imagem/HTML; use uma captura do Windows se necessário. |
| Guia permanece na conexão | Instale/ative/recarregue a extensão no perfil correto e repita a operação pelo aplicativo. |
| Movidesk não preenche | Confira login, visibilidade do formulário, campos exigidos e **Detalhes** no rodapé. |
| Categoria/urgência não corresponde ao esperado | Revise as opções do formulário e selecione manualmente o valor adequado à instância. |
| Número não retorna | Mantenha aplicativo e guia abertos; confira prazo, URL/modal e digite o número manualmente se necessário. |
| Retorno interrompido ou guia não localizada | Informe o ticket salvo. Para outro formulário, confira a guia anterior e use a ação de recuperação em **Pendências**. |
| Retornou um número diferente do já informado | Confira o chamado correto antes de ajustar o campo **Ticket**. |
| Porta 18764 ocupada | Feche outra instância do NOCFlow e tente novamente. |
| Rascunho não salva | Verifique espaço e permissão no diretório `.noc_data`; consulte o rodapé e os detalhes. |

Ao investigar uma falha, registre a ação realizada, a mensagem em **Detalhes** e o trecho pertinente de `noc.log`. Os logs têm rotação automática. Mudanças nos layouts dos sistemas podem exigir atualização dos seletores pela manutenção do projeto.
