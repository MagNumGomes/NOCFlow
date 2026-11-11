# Proposta de evolução operacional do NOCFlow

## Objetivo e alcance

Transformar o NOCFlow em um assistente de acompanhamento operacional: receber ocorrências, aplicar regras de atendimento, preparar registros, organizar acionamentos e manter a continuidade entre turnos.

Esta proposta reúne conclusões generalizadas de uma revisão documental de onboarding e procedimentos operacionais. Não reproduz cadastros, contratos, credenciais, contatos, ambientes, horários ou exemplos reais. Os recursos descritos como propostas ainda precisam ser implementados.

A revisão considerou o inventário e a estrutura dos documentos Markdown, com aprofundamento nos fluxos de atendimento, exceções, rotinas, escalonamento e registros. As planilhas foram inventariadas estruturalmente; o conteúdo visual de imagens e os documentos externos referenciados não foram validados. Não houve validação em produção nem auditoria integral do repositório para publicação.

## 1. Diagnóstico

O aplicativo atual atende principalmente à importação do Zabbix, preparação do Movidesk e cópia de comunicados. A operação documentada exige também:

- Triagem de chamados existentes e solicitações recebidas em canais de comunicação.
- Regras diferentes conforme serviço, severidade, horário, calendário e modalidade de operação.
- Cobranças, tentativas de contato, confirmação de ciência e acompanhamento de previsões.
- Checklists periódicos, verificações de dashboards e acompanhamento de processos agendados.
- Registro em mais de um sistema e vínculo entre seus identificadores.
- Passagem de turno, diário de bordo e acompanhamento pós-incidente.
- Consulta rápida a procedimentos, incluindo exceções ao fluxo geral.

Há uma boa base documental: trilha de aprendizagem, guias de ferramentas, matrizes de responsabilidade, instruções de trabalho e modelos de incidentes. A maior oportunidade é converter essas informações em apoio contextual e tarefas rastreáveis.

## 2. Consolidar regras antes de automatizar decisões

Os documentos examinados apresentam orientações gerais, exceções locais, modelos ainda não preenchidos e divergências registradas. Esses conteúdos precisam ter estados e precedência explícitos.

### Questões a resolver

| Tema | Problema identificado na documentação | Evolução proposta |
|---|---|---|
| Encerramento | A orientação geral de encaminhar sem encerrar convive com fluxos específicos que permitem concluir o registro após determinadas ações. | Política de encerramento por tipo de atendimento e perfil operacional. |
| Agrupamento | Existem regras de novo chamado, atualização e exceções de agrupamento. | Separar identidade do evento, agrupamento operacional e política de criação de tickets. |
| Prioridade | A equivalência entre severidade e urgência possui exceções. | Preservar severidade original e registrar prioridade aplicada com motivo e regra. |
| Prazos | Há prazos divergentes e marcos diferentes para iniciar a contagem. | Definir separadamente prazo de registro, notificação, primeira resposta e acompanhamento. |
| Responsabilidade | Materiais gerais, trilhas de treinamento e runbooks podem sugerir níveis diferentes de atuação. | Indicar papel executor, escopo, modalidade de operação e condições de aplicabilidade. |
| Rotinas | Há tarefas incompletas e verificações descritas de forma subjetiva. | Definir entrada, resultado esperado, evidência e destino em caso de falha. |
| Matrizes | Há transcrições de tabelas com campos ausentes ou desalinhados. | Manter como pendência de validação; não inferir contato ou ordem de acionamento. |
| Revisão | Datas e responsáveis nem sempre estão preenchidos; conteúdos aparecem em mais de um local. | Uma fonte canônica por regra, versão, vigência e referências nas páginas auxiliares. |

Uma diferença pode representar uma exceção legítima. O sistema deve mostrar a aplicabilidade e a origem da regra, sem escolher uma orientação apenas por ser a mais recente.

### Modelo proposto de regra

- Identificador estável e versão.
- Perfil operacional e serviço aplicáveis.
- Condições: origem, tags, família do alerta, severidade, calendário e turno.
- Resultado: prioridade, equipe de destino, canais, próximos passos e prazos.
- Política de criação, agrupamento e encerramento de chamados.
- Fonte, responsável pela manutenção e período de vigência.
- Estado: rascunho, validada, suspensa ou substituída.
- Precedência explícita entre regra geral e exceção.

Se faltarem dados ou duas regras forem incompatíveis, apresentar a pendência e as fontes. Uma configuração incompleta não deve se transformar silenciosamente em uma decisão operacional.

## 3. Funcionalidades prioritárias

### 3.1 Atendimento multicanal

Adicionar entrada manual e por texto colado, com origem Zabbix, Grafana, Teams, WhatsApp, e-mail ou telefone. Distinguir incidente, solicitação, encaminhamento, mudança e rotina.

Campos sugeridos:

- Resumo, relato original e origem.
- Serviço, ambiente e ativo quando aplicáveis.
- Perfil operacional, impacto relatado e prioridade.
- Referências externas: sistema, instância, identificador e URL.
- Responsável pelo acompanhamento e próxima ação.

Um atendimento por telefone não deve depender de host ou evento Zabbix. Um chamado existente deve poder ser vinculado para triagem, sem abrir outro automaticamente.

### 3.2 Linha do tempo e acionamentos

Registrar eventos com horário, autor, canal, destinatário e resultado:

1. Recebimento e triagem.
2. Criação ou vínculo do chamado.
3. Preparação da comunicação.
4. Envio registrado.
5. Tentativa de contato e confirmação de ciência.
6. Retorno técnico e previsão informada.
7. Cobrança, reescalonamento e normalização observada.
8. Validação final e conclusão conforme a política aplicável.

Copiar uma mensagem, registrar seu envio e obter confirmação são fatos distintos. Quando não houver integração de entrega, a interface deve identificar o envio como registro manual do operador.

Manter separados: estado do alerta, estado remoto do ticket, situação do acompanhamento e arquivamento local. Normalização do alerta não comprova, sozinha, validação do serviço ou encerramento do chamado.

### 3.3 Agenda de turno e acompanhamento

Uma tela inicial deve responder:

- O que exige ação agora?
- Qual acionamento está sem resposta?
- Qual previsão venceu?
- Qual rotina precisa ser executada?
- O que precisa ser passado ao próximo turno?

Suportar horários fixos, intervalos, dias úteis, feriados, fuso horário e dependências entre tarefas. Persistir os vencimentos e recalculá-los ao reabrir o aplicativo. Rotinas não executadas devem continuar identificadas como pendentes ou vencidas.

Cada execução de checklist precisa manter seu próprio registro. Evitar reutilizar o resultado do dia anterior como se fosse uma nova verificação.

### 3.4 Monitoramento de dashboards e processos agendados

Cadastrar, na configuração privada, grupos de dashboards e processos recorrentes. Cada item deve informar:

- O que observar e em qual período.
- Resultado esperado e significado de ausência de dados.
- Horário previsto, duração esperada e tolerância quando definidos.
- Dependências entre etapas.
- Evidência necessária e encaminhamento em caso de falha.

Substituir instruções como “verificar algo fora do normal” por critérios específicos de cada painel. Cor, ausência de dados ou falha de ping devem ser interpretadas no contexto do serviço, e não como prova universal de indisponibilidade.

### 3.5 Regras para chamados e eventos relacionados

A identidade atual por instância e evento deve ser preservada. Acrescentar uma relação entre vários eventos e um atendimento, mantendo todos os eventos e suas evidências individualmente.

Antes de propor novo ticket ou atualização, considerar a política configurada, severidade original, prioridade aplicada, natureza da ocorrência, janela de agrupamento e situação conhecida do chamado.

Se a decisão depender de interações do ticket que o aplicativo não consegue consultar, solicitar essa informação ao operador. Correlacionar eventos não significa automaticamente consolidar seus chamados.

### 3.6 Comunicação contextual

Expandir os modelos de abertura para incluir acionamento, atualização, cobrança, transferência de turno, normalização e encerramento aplicável.

A necessidade de ticket antes da comunicação deve ser configurável. A opção de acionamento inicial com “ticket em abertura” só se aplica aos fluxos que permitirem essa sequência.

Preparar textos diferentes para destinatários internos e externos. Usar campos estruturados para ticket, serviço, impacto, ações, previsão e próxima atualização. Preservar texto estruturado no Movidesk mesmo quando houver imagem anexada.

### 3.7 Diário de bordo e passagem de turno

Gerar o diário a partir da linha do tempo, com seleção do período. Para a passagem, reunir:

- Atendimentos em acompanhamento.
- Equipes acionadas e confirmação de ciência.
- Último retorno, previsão e próxima ação.
- Rotinas pendentes e falhas das ferramentas operacionais.
- Responsável pela continuidade e registro de recebimento do turno.

As regras de inclusão devem ser explícitas: a equipe técnica já estar atuando não elimina necessariamente a necessidade de acompanhamento pelo próximo operador.

### 3.8 Incidentes maiores e pós-incidente

Como evolução posterior, oferecer um registro de sala de coordenação com participantes por papel, links, linha do tempo, decisões, comunicação e pendências.

Separar serviço restabelecido, resolução definitiva, causa confirmada e investigação pendente. Acompanhar ações corretivas com responsável e prazo, conforme o procedimento aplicável.

## 4. Uso adequado de IA

### Prioridade A — Organizar relatos

Receber texto colado ou anotação de ligação e sugerir resumo, serviço, impacto relatado, ações realizadas, informações faltantes e descrição do chamado.

Exemplo inteiramente fictício:

> “O serviço de exemplo continua indisponível. A equipe técnica informou que está investigando e ainda não forneceu previsão.”

Saída esperada:

- Situação relatada: indisponibilidade permanece.
- Equipe: equipe técnica, sem identificação adicional.
- Ação informada: investigação em andamento.
- Previsão: não informada.
- Pendência: obter atualização conforme o prazo configurado.

A IA não deve transformar relato em fato confirmado por monitoramento. Preservar a mensagem original e identificar a origem de cada informação sugerida.

### Prioridade B — Consultar procedimentos com fontes

Permitir perguntas como “qual procedimento se aplica a este tipo de ocorrência?”. Recuperar somente documentos aplicáveis ao perfil, serviço e versão vigente e responder com a referência da seção utilizada.

O mecanismo de regras calcula destino e prazos; a IA explica a orientação e ajuda a localizar o procedimento. Divergências documentais devem aparecer como divergências, sem uma conclusão inventada.

Começar com busca textual e filtros de metadados. Acrescentar busca semântica se a avaliação mostrar ganho. Não é necessário treinar um modelo com a wiki para oferecer esse recurso.

### Prioridade C — Resumos de turno e de incidentes

Usar apenas eventos registrados para preparar resumo, ações executadas, pendências e próximos passos. Cada afirmação relevante deve permitir consultar o registro de origem.

Datas, números de tickets, destinatários e prazos devem vir de dados estruturados. A IA não deve calcular SLA nem preencher causa raiz sem evidência.

### Prioridade D — Apoio à qualidade documental

Identificar campos não preenchidos, instruções ambíguas, duplicações e aparentes conflitos de procedimentos. Produzir sugestões de revisão, mantendo a decisão sobre a regra com seu responsável.

### Relatórios: cálculo determinístico, redação assistida

Contagens, agrupamentos, tempos e percentuais devem ser calculados por código sobre dados completos, com período, filtros e denominadores registrados. Uma consulta limitada aos itens mais frequentes não equivale necessariamente ao total do período.

A IA pode redigir a explicação dos resultados já calculados, destacando recorrências e pendências sem atribuir causas não documentadas.

### Integração e avaliação

- Serviço de IA independente dos widgets e da execução de regras.
- Respostas estruturadas e validadas antes de preencher sugestões.
- Solicitações restritas ao conteúdo necessário; documentos e mensagens tratados como dados, não como instruções do sistema.
- Base privada e índices derivados armazenados fora do conteúdo público.
- Escolha de provedor ou execução local conforme o ambiente de uso e o tratamento permitido para os dados.
- Medição de tempo economizado, correções, afirmações sem fonte, latência e custo por tarefa.

## 5. Organização técnica sugerida

| Componente proposto | Responsabilidade |
|---|---|
| `regras_operacionais` | Aplicabilidade, precedência, prioridade, encaminhamento e critérios de conclusão. |
| `agenda_operacional` | Calendários, fusos, recorrência, vencimentos e próxima ação. |
| `historico_atendimento` | Linha do tempo, tentativas, retornos e evidências. |
| `perfis_operacionais` | Carregamento e validação de configurações privadas. |
| `base_conhecimento` | Documentos, metadados, busca, referências e versões. |
| `assistente_ia` | Organização de relatos, explicações e resumos fundamentados. |
| `relatorios` | Indicadores reproduzíveis e exportações. |

Separar progressivamente as telas do controlador atual. Para histórico crescente, considerar SQLite com migração do rascunho existente e evidências em arquivos. Uso simultâneo por vários operadores exige um serviço compartilhado; um banco local isolado não oferece essa colaboração.

Manter a extensão atual como integração disponível. Avaliar APIs oficiais por conector quando houver acesso, necessidade de consulta de status e viabilidade técnica. Uma consulta indisponível deve resultar em informação desconhecida, e não em status presumido.

## 6. Documentação e publicação no GitHub

### Conteúdo público proposto

```text
docs/
  operacao/
    visao-geral.md
    fluxo-atendimento.md
    escalonamento.md
    rotinas-turno.md
    comunicacao.md
    uso-ia.md
  templates/
    procedimento.md
    passagem-turno.md
    registro-incidente.md
config/
  schemas/
  examples/
    perfil-demonstracao.json
```

O repositório público deve conter implementação genérica, contratos de configuração e exemplos construídos do zero. Os perfis reais são fornecidos em diretório externo à instalação ou ao checkout.

### Atualizações documentais

- Uma fonte canônica por processo; guias de onboarding devem referenciá-la.
- Metadados padronizados: identificador, versão, estado, aplicabilidade, responsável por papel e revisão.
- Marcar modelos incompletos como modelos, sem apresentá-los como procedimentos operacionais vigentes.
- Runbooks curtos: gatilho, pré-condições, passos, resultado esperado, evidências e encaminhamento.
- Distinguir competências do treinamento de permissões de atuação na operação.
- Atualizar exemplos técnicos: métricas acumuladas de processo não equivalem a percentual instantâneo de CPU; ausência de ping não basta para afirmar servidor desligado; arquivo de backup existente não comprova restauração.
- Testar o onboarding com cenários sintéticos: falta de dados, ausência de retorno, exceção de prioridade, conflito de regra e passagem de turno.

### Proteção do conteúdo publicado

Não copiar a wiki interna para o repositório público. Além de senhas e tokens, manter fora dele nomes e contatos reais, URLs internas, hosts, topologias, escalas, condições contratuais, protocolos, capturas reais e informações pessoais ou administrativas.

Usar domínios reservados, como `example.com`, nomes sintéticos e regras demonstrativas sem correspondência com a operação real. Trocar apenas o nome do cliente não anonimiza uma topologia, um histórico ou uma combinação de horários e serviços.

Antes da publicação, verificar conteúdo versionado, histórico Git, fixtures, documentação, manifesto da extensão, scripts gerados, logs, imagens, metadados e artefatos de distribuição. O `.gitignore` não remove arquivos já rastreados nem apaga versões anteriores. Verificações de segredos ajudam, mas não detectam sozinhas todo dado identificável.

O build público deve ser produzido a partir de configuração demonstrativa e incluir somente recursos explicitamente previstos. Dados operacionais, bases de busca e históricos devem permanecer externos ao pacote.

## 7. Sequência recomendada

| Etapa | Entrega | Critério de conclusão |
|---|---|---|
| 1 | Catálogo de regras e metadados | Regras têm aplicabilidade e origem; conflitos e lacunas ficam explícitos. |
| 2 | Histórico e acompanhamento | Cópia, envio, ciência e retorno são distintos e persistem após reinício. |
| 3 | Agenda de turno | Rotinas e cobranças consideram calendário, fuso e próxima ação. |
| 4 | Entrada multicanal e IA de relatos | Sugestões preservam a origem e não preenchem dados desconhecidos como fatos. |
| 5 | Consulta de procedimentos e passagem de turno | Respostas e resumos mostram as fontes usadas. |
| 6 | Indicadores e integrações adicionais | Resultados são reproduzíveis e vinculados aos registros de origem. |

Indicadores iniciais: tempo entre recebimento e registro, tempo até notificação, tempo até ciência da equipe, acompanhamentos vencidos, execução pontual de rotinas, pendências recebidas pelo turno seguinte e correções necessárias nas sugestões da IA.

## Conclusão

A próxima evolução de maior valor combina regras operacionais configuráveis, linha do tempo e agenda de acompanhamento. A IA complementa essa estrutura organizando linguagem livre, localizando procedimentos e resumindo registros com fontes. Essa separação permite tornar o projeto reutilizável e publicável, mantendo os dados reais da operação em configuração privada.
