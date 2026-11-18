# NOCFlow

Aplicativo desktop para Windows criado para apoiar equipes de **NOC (Network Operations Center)** no registro, triagem, acompanhamento e comunicação de incidentes e solicitações operacionais.

---

## 📖 Documentação do Projeto

- 📘 **[Manual de Uso Completo](docs/manual.md)** — Guia passo a passo de todas as telas, atalhos, extensão do navegador, Central Operacional, relatórios e solução de problemas.
- 🏗️ **[Arquitetura Técnica](docs/arquitetura.md)** — Estrutura dos módulos, contratos de dados, concorrência, segurança da ponte local, persistência e ciclo de manutenção.

---

## 🌐 O que é um NOC e onde o NOCFlow atua?

- **Para quem ainda não conhece a área:** um **NOC (Centro de Operações de Rede)** funciona como a "torre de controle" da tecnologia de uma empresa. Analistas acompanham painéis de monitoramento (como o *Zabbix*) 24 horas por dia. Quando um servidor, banco de dados ou serviço apresenta falha, o operador precisa rapidamente entender o alerta, capturar a evidência, abrir um chamado no sistema de atendimento (como o *Movidesk*), acionar o time técnico responsável (via *WhatsApp*, *Microsoft Teams* ou *E-mail*) e acompanhar o caso até a normalização.
- **Para quem já vive a rotina de NOC:** o NOCFlow atua exatamente na ponte entre o **monitoramento**, o **sistema de tickets** e os **canais de comunicação**. Ele elimina o trabalho braçal de copiar, colar, recortar prints e formatar mensagens repetidas, mantendo uma fila local organizada com histórico, regras de atendimento por cliente/perfil e passagem de turno estruturada — tudo com **abordagem local primeiro (sem depender de IA para o fluxo principal)**.

---

## 🎯 Dores da Operação e Como o NOCFlow Resolve

| Dor comum na rotina do NOC | Como o NOCFlow resolve |
|---|---|
| **Trabalho repetitivo de copiar e colar** entre Zabbix, Movidesk, WhatsApp, Teams e E-mail a cada alerta. | Importa os dados direto da página do Zabbix (individual ou em lote de até 100 eventos) com 1 clique e já monta o ticket e os comunicados padronizados para cada canal. |
| **Abertura lenta de chamados**, exigindo preencher título, tipo interno, categoria, urgência, solicitante, serviço, horas e colar print manualmente. | A extensão no Microsoft Edge seleciona e confirma o tipo Interno antes de preencher título, descrição com link + print, categoria, urgência, solicitante/serviço (via tags) e apontamento padrão (`00:03` / `Observability`), devolvendo o número do ticket salvo ao incidente de origem. |
| **Perda de contexto ao atender vários incidentes ao mesmo tempo**, misturando prints, números de chamados ou rascunhos. | Fila local persistente com salvamento automático: cada incidente guarda seus próprios campos, imagem, recortes, linha do tempo e vínculo de retorno do ticket, mesmo que você troque de item enquanto trabalha. |
| **Alertas que chegam apenas por print de tela** em grupos ou conversas, obrigando o operador a digitar tudo manualmente. | Leitura instantânea por **OCR nativo do Windows** (offline e sem custo de tokens), extraindo Host, Trigger, Severidade, Dados Operacionais e Horário diretamente da imagem copiada (`Win+Shift+S`), com opção de complemento por IA apenas para lacunas. |
| **Edição manual demorada de prints** para destacar apenas Host, Trigger e Severidade em comunicados de e-mail. | Editor visual integrado de recortes com zoom e geração automática da tabela renderizada direto do Zabbix. |
| **Dúvidas sobre regras específicas de cada cliente/ambiente** (horários de plantão, quando abrir novo ticket ou vincular, quem acionar). | **Central Operacional** com motor determinístico de regras por perfil, janelas de calendário/fuso, alerta de conflitos e busca local em base de conhecimento de procedimentos. |
| **Esquecimento de cobranças (follow-up), checklists de turno e passagens de plantão incompletas.** | Agenda de rotinas recorrentes com aviso de vencimento no topo do app, linha do tempo por atendimento, auditoria de alertas recorrentes e geração automática de **Diário de Bordo**, **Passagem de Turno** e relatórios em **CSV/PDF**. |

---

## ✨ Principais Recursos

- **Importação direta do Zabbix:** coleta estruturada de alertas individuais ou em lote pela extensão do Microsoft Edge ou via JSON/Tampermonkey, incluindo captura automática da tabela de evidência e leitura de tags de solicitante e serviço.
- **Preenchimento assistido no Movidesk:** automação na sessão já autenticada do navegador do operador, com preservação da assinatura do agente e captura automática do protocolo gerado.
- **Atendimento multicanal e fila inteligente:** busca instantânea, filtros por etapa e severidade, proteção de campos revisados manualmente, histórico de eventos e arquivamento.
- **Comunicados prontos e assinatura no WhatsApp Web:** templates para WhatsApp, Teams e E-mail (*Abertura normal*, *Abertura inicial*, *Acionamento*, *Atualização* e *Normalização*), além de popup na extensão para assinar mensagens direto no WhatsApp Web sem envio acidental.
- **Central Operacional integrada:** avaliação de regras por perfil, agenda de rotinas de turno, consulta a procedimentos locais, auditoria de recorrência e exportação de relatórios em PDF e CSV.
- **Destinatários por empresa:** cadastro local de múltiplos e-mails em Para e Cc, seleção por dropdown, edição/exclusão e botões separados para copiar cada lista em **Comunicar → E-mail**.
- **OCR local + IA sob demanda:** fluxo principal 100% local e gratuito; integração opcional com **Groq** e **Google Gemini** apenas quando solicitada para completar capturas difíceis, estruturar relatos livres ou resumir procedimentos citando fontes.

---

## 🛠️ Tecnologias Utilizadas

- **Aplicativo Desktop e Interface:**
  - **Python 3.10+** — linguagem principal da aplicação e das regras de negócio.
  - **Tkinter / TTK** — interface gráfica nativa para Windows, leve e responsiva, com execução assíncrona desacoplada por filas e workers.
- **OCR, Imagens e Área de Transferência:**
  - **WinRT (`Windows.Media.Ocr`)** — reconhecimento óptico de caracteres nativo do Windows 10/11 (offline).
  - **Pillow (PIL)** — manipulação, miniatura e montagem de recortes de evidências.
  - **Win32 Clipboard API (`ctypes`) e `pyperclip`** — publicação nativa de imagens (`CF_DIB`) e textos na área de transferência.
- **Integração com Navegador:**
  - **JavaScript (ES Modules)** e **Microsoft Edge Extension (Manifest V3)** — coleta no Zabbix, automação no Movidesk e assinatura no WhatsApp Web.
  - **Ponte HTTP Local (`127.0.0.1`)** — servidor loopback autenticado por tokens descartáveis para comunicação segura entre o app e o navegador.
  - **html2canvas** e **Tampermonkey** — renderização de tabelas HTML em PNG e userscripts opcionais.
- **Persistência e Relatórios:**
  - **JSON Atômico** — armazenamento local versionado de rascunhos, fila, histórico e agenda com escrita segura (`flush` + `fsync`).
  - **ReportLab** — exportação local de relatórios operacionais e de recorrência em arquivos PDF paginados.
- **Inteligência Artificial Opcional:**
  - **Groq SDK** — estruturação de texto, organização de relatos e consulta a procedimentos com validação estrita de JSON Schema.
  - **Google Gemini SDK** — leitura visual complementar sob demanda para capturas incompletas.

---

## 🚀 Guia Completo: Como Baixar, Instalar e Deixar Tudo Pronto para Rodar

Você só precisa de um computador com **Windows 10 ou 11** e do navegador **Microsoft Edge** (onde você já acessa o Zabbix e o Movidesk).

---

### Parte 1: Obter o Aplicativo e Colocar na Área de Trabalho

Escolha **apenas uma** das duas opções abaixo conforme o que você tem em mãos:

#### Opção A — Você já recebeu a pasta pronta (`NOCFlow`)
1. **Extraia ou copie a pasta `NOCFlow` inteira** para o seu computador (por exemplo, em *Documentos* ou na *Área de Trabalho*).
   > ⚠️ **Importante:** nunca tire o arquivo `NOCFlow.exe` sozinho de dentro da pasta dele; ele precisa continuar ao lado da subpasta `_internal`.
2. **Crie o atalho na sua Área de Trabalho:**
   - Clique com o **botão direito** sobre o arquivo **`NOCFlow.exe`**.
   - Clique em **`Mostrar mais opções`** → **`Enviar para`** → **`Área de trabalho (criar atalho)`**.
3. Dê dois cliques no atalho **`NOCFlow`** criado na sua Área de Trabalho para abrir o aplicativo.

#### Opção B — Você baixou o projeto pelo GitHub (Código-Fonte)
1. **Instale o Python (se ainda não tiver):**
   - Baixe o **Python 3.10 ou superior** em [python.org/downloads](https://www.python.org/downloads/).
   - ⚠️ Na primeira tela do instalador, **marque a caixinha `"Add python.exe to PATH"`** na parte inferior antes de clicar em *Install Now*.
2. **Baixe o projeto do GitHub ([github.com/MagNumGomes/NOCFlow](https://github.com/MagNumGomes/NOCFlow)):**
   - **Pelo Terminal com `git clone`:** abra o PowerShell na pasta onde deseja salvar (por exemplo, na Área de Trabalho) e execute:
     ```powershell
     git clone https://github.com/MagNumGomes/NOCFlow.git
     cd NOCFlow
     ```
   - **Sem Git (baixando o ZIP pelo navegador):** acesse [https://github.com/MagNumGomes/NOCFlow](https://github.com/MagNumGomes/NOCFlow), clique no botão verde **`<> Code`** → **`Download ZIP`**, clique com o botão direito no arquivo `.zip` baixado, escolha **`Extrair Tudo...`** e abra a pasta extraída.
3. **Gere o aplicativo pronto com ícone na Área de Trabalho (1 clique):**
   - Dentro da pasta do projeto, abra a subpasta **`scripts`** e dê dois cliques em **`Build Windows.cmd`**.
   - Aguarde cerca de 1 minuto enquanto ele instala tudo e empacota o programa automaticamente.
   - Ao terminar, aparecerá a mensagem **`Atalho criado na Area de Trabalho`**. Basta dar dois cliques no ícone **`NOCFlow`** que surgiu na sua Área de Trabalho!
    - *(Alternativa rápida pelo terminal sem gerar executável: clique com o botão direito na pasta do projeto → **Abrir no Terminal** e rode `python -m venv .venv`, `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` e `.\.venv\Scripts\python.exe app_noc.py`. O `.env` é preparado automaticamente, preservando configurações existentes.)*

---

### Parte 2: Configurar os Domínios do Movidesk e do Zabbix (Obrigatório na 1ª vez)

> ⚠️ **Importante:** Por segurança e privacidade, o projeto publicado no GitHub vem apenas com endereços fictícios de exemplo (`https://empresa.movidesk.com` e `https://zabbix.example.com`). Para que o aplicativo e a extensão funcionem no seu ambiente, **você deve informar manualmente os domínios reais da sua empresa** seguindo os dois passos abaixo:

1. **Colocar o domínio do seu Movidesk (e chaves opcionais de IA):**
   - Com o **NOCFlow** aberto, clique no menu **`⋯`** (canto superior direito) e escolha **`Configurações`** *(ou dê dois cliques em `Abrir configuracoes.cmd`)*.
   - O Bloco de Notas abrirá o arquivo `.env`.
   - Localize a linha `MOVIDESK_URL=https://empresa.movidesk.com` e troque pelo endereço real do Movidesk da sua empresa (sem barra no final):
     ```ini
     MOVIDESK_URL=https://suaempresa.movidesk.com
     ```
   - *(Opcional)* Na linha `NOME_OPERADOR=`, informe seu nome (ex.: `NOME_OPERADOR=João Vitor`) para assinar automaticamente os comunicados de WhatsApp.
   - *(Opcional)* Se quiser usar Inteligência Artificial para complementar prints ou organizar relatos, preencha `GROQ_API_KEY=` e/ou `GEMINI_API_KEY=`. O fluxo normal do app **não** exige chaves de IA.
   - Salve o arquivo no Bloco de Notas (**`Ctrl+S`**) e feche-o.

2. **Colocar o domínio do seu Zabbix:**
   - Após abrir o NOCFlow pela primeira vez, ele cria automaticamente um arquivo chamado **`extensao.json`** para guardar os endereços do seu Zabbix sem expô-los no Git.
   - Para abri-lo facilmente:
     - **Se estiver usando o executável (atalho da Área de Trabalho):** pressione as teclas **`Win + R`** no teclado, digite `notepad %LOCALAPPDATA%\NOCFlow\.noc_data\extensao.json` e aperte **`Enter`**.
     - **Se estiver rodando pelo código-fonte no terminal:** abra com o Bloco de Notas o arquivo `.noc_data\extensao.json` dentro da pasta do projeto.
   - Substitua os endereços de exemplo (`https://zabbix.example.com`) pelo(s) endereço(s) real(is) do Zabbix da sua empresa (apenas `https://` + domínio, sem `/` ou caminhos no final):
     ```json
     {
       "zabbix_origens": [
         "https://zabbix.suaempresa.com.br",
         "https://zabbix-secundario.suaempresa.com.br"
       ]
     }
     ```
   - Salve no Bloco de Notas (**`Ctrl+S`**), feche o arquivo e **feche e abra novamente o NOCFlow** (ao iniciar, o NOCFlow injetará automaticamente os seus domínios reais na cópia local da extensão).

---

### Parte 3: Instalar a Extensão no Microsoft Edge

A extensão é o que permite ao NOCFlow ler os alertas do Zabbix com 1 clique, preencher o ticket no Movidesk sozinho e assinar mensagens no WhatsApp Web. Você só precisa instalá-la **uma única vez**:

1. Com o NOCFlow aberto, clique no menu **`⋯`** (canto superior direito) e escolha **`Instalar extensão do Edge`**.
2. Na janela que se abrir:
   - Clique no botão **`Copiar caminho`**.
   - Clique no botão **`Abrir extensões`** (isso abrirá a página `edge://extensions/` no seu Microsoft Edge).
3. Na página de extensões do Microsoft Edge:
   - Ative a chavinha **`Modo do desenvolvedor`** (geralmente fica no menu lateral esquerdo ou no canto superior direito).
   - Clique no botão **`Carregar sem compactação`** (ou *Load unpacked*).
4. Na janela de seleção de pasta que abrir:
   - Clique na barra de endereço no topo da janela, pressione **`Ctrl+V`** para colar o caminho copiado, aperte **`Enter`** e clique no botão **`Selecionar pasta`**.
5. Confirme que o cartão **`NOCFlow — Zabbix e Movidesk`** apareceu na lista e está com a chavinha **ativada**.
6. **Dica para usar no WhatsApp Web:** clique no ícone de **quebra-cabeça (🧩 Extensões)** no topo direito do Edge e clique no **ícone de olho/alfinete** ao lado de *NOCFlow* para deixá-lo visível na barra do navegador.

---

### Parte 4: Tudo Pronto! Como Rodar o Seu Primeiro Atendimento

Agora que o aplicativo e a extensão estão instalados, veja como usar no dia a dia:

1. **Verifique seu login:** no Microsoft Edge, deixe abertas e logadas as páginas do seu **Zabbix** e do **Movidesk** (e aperte **`F5`** nelas caso já estivessem abertas antes de instalar a extensão).
2. **Conecte o Zabbix ao NOCFlow:**
   - Na faixa superior do NOCFlow, clique no botão **`Conectar`**.
   - Uma guia rápida se abrirá no Edge dizendo *"NOCFlow conectado"*. Você já pode fechar essa guia de confirmação. O status no aplicativo mudará para **`Zabbix: conectado`**.
3. **Envie um alerta do Zabbix para o NOCFlow:**
   - Entre em um evento no Zabbix (ou na lista de problemas).
   - No canto inferior esquerdo da página, clique na barra escura **`▼ NOCFlow — Zabbix e Movidesk`** para expandir os botões.
   - Clique em **`Enviar ao NOCFlow`**. Os dados e o print da tabela do alerta aparecerão instantaneamente dentro do aplicativo!
4. **Abra o chamado preenchido no Movidesk:**
   - Confira os dados na aba **Incidente** do NOCFlow e clique no botão **`Criar ticket`** (canto inferior direito).
   - O Edge abrirá a tela de novo ticket no Movidesk e preencherá sozinho: **Título, Tipo Interno, Categoria, Urgência, Solicitante/Serviço (pelas tags), Tempo Apontado (`00:03`), Atividade (`Observability`) e Descrição com o Link + Print do alerta**!
   - Revise e clique em **Salvar** no Movidesk: o número do ticket salvo voltará sozinho para o campo **Ticket** do NOCFlow.
5. **Copie os comunicados:**
   - Vá na aba **`Comunicar`** do NOCFlow, escolha **WhatsApp**, **Teams** ou **E-mail**, clique em **`Copiar mensagem`** e cole no grupo ou conversa do atendimento.

Para explorar recursos avançados — como recortes de imagem, leitura de prints avulsos com OCR (`Win+Shift+S`), regras por cliente, agenda de rotinas e relatórios em PDF na **Central Operacional** — consulte o **[Manual de Uso Completo](docs/manual.md)**.

## Desenvolvimento e validação

No ambiente com `requirements-dev.txt` instalado:

```powershell
python -m playwright install chromium --no-shell
$env:NOC_TEST_BROWSER = "1"
python -m unittest discover -s tests -v
python -m ruff check .
python scripts/verificar_build.py
```

O verificador executa OCR/Tkinter/PDF/ponte offline e grava `build/verificacao-fonte.json`.
Para homologar o pacote sem copiar dados pessoais ou criar atalhos:

```powershell
.\build.ps1 -SomentePacote -PastaSaida dist
```

Diagnóstico local: `.noc_data/logs/noc.jsonl` (rotação automática). A aplicação permite uma instância por diretório de dados.
