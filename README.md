# NOCFlow

Aplicativo desktop para Windows criado para apoiar equipes de **NOC (Network Operations Center)** no registro, triagem, acompanhamento e comunicação de incidentes e solicitações operacionais.

---

## 📖 Documentação do Projeto

- 📘 **[Manual de Uso](docs/manual.md)** — Guia direto de telas, atalhos, extensão do navegador, comunicação, Central Operacional e solução de problemas.
- 🏗️ **[Arquitetura Técnica](docs/arquitetura.md)** — Visão direta dos módulos, fluxos Zabbix/Movidesk, segurança local (DPAPI/loopback), persistência e manutenção.
- 📦 **[Dependências, CI e Releases](docs/releases.md)** — Snapshot homologado com hashes, CI Windows, auditoria `pip-audit`, versão única e publicação assinada.

---

## 🌐 O que é um NOC e onde o NOCFlow atua?

- **Para quem ainda não conhece a área:** um **NOC (Centro de Operações de Rede)** funciona como a "torre de controle" da tecnologia de uma empresa. Analistas acompanham painéis de monitoramento (como o *Zabbix*) 24 horas por dia. Quando um servidor, banco de dados ou serviço apresenta falha, o operador precisa rapidamente entender o alerta, capturar a evidência, abrir um chamado no sistema de atendimento (como o *Movidesk*), acionar o time técnico responsável (via *WhatsApp*, *Microsoft Teams* ou *E-mail*) e acompanhar o caso até a normalização.
- **Para quem já vive a rotina de NOC:** o NOCFlow atua exatamente na ponte entre o **monitoramento**, o **sistema de tickets** e os **canais de comunicação**. Ele elimina o trabalho braçal de copiar, colar, recortar prints e formatar mensagens repetidas, mantendo uma fila local organizada com histórico, regras de atendimento por cliente/perfil e passagem de turno estruturada — tudo com **abordagem local primeiro (sem depender de IA para o fluxo principal)**.

---

## 🎯 Dores da Operação e Como o NOCFlow Resolve

| Dor comum na rotina do NOC | Como o NOCFlow resolve |
|---|---|
| **Trabalho repetitivo de copiar e colar** entre Zabbix, Movidesk, WhatsApp, Teams e E-mail a cada alerta. | Importa os dados direto da página do Zabbix (individual ou em lote de até 100 eventos) com 1 clique e já monta o ticket e os comunicados padronizados para cada canal. |
| **Abertura lenta de chamados**, exigindo preencher título, tipo interno, categoria, urgência, solicitante, serviço, horas e colar print manualmente. | A extensão no Microsoft Edge seleciona e confirma o tipo Interno antes de preencher título, descrição com link + print (com 1 linha em branco antes da assinatura), categoria, urgência, solicitante/serviço (via tags) e apontamento padrão (`00:03` / `Observability`), devolvendo o número do ticket salvo ao incidente de origem. |
| **Perda de contexto ao atender vários incidentes ao mesmo tempo**, misturando prints, números de chamados ou rascunhos. | Fila local persistente e criptografada com DPAPI: cada incidente guarda seus próprios campos, imagem, recortes, linha do tempo e vínculo de retorno do ticket, mesmo que você troque de item enquanto trabalha. |
| **Alertas que chegam apenas por print de tela** em grupos ou conversas, obrigando o operador a digitar tudo manualmente. | Leitura instantânea por **OCR nativo do Windows** (offline e sem custo de tokens), extraindo Host, Trigger, Severidade, Dados Operacionais e Horário diretamente da imagem copiada (`Win+Shift+S`), com opção de complemento por IA apenas para lacunas. |
| **Edição manual demorada de prints** para destacar apenas Host, Trigger e Severidade em comunicados de e-mail. | Editor visual integrado de recortes com zoom, barra rápida de anexo na aba Comunicar e geração automática da tabela renderizada direto do Zabbix. |
| **Dúvidas sobre regras específicas de cada cliente/ambiente** (horários de plantão, quando abrir novo ticket ou vincular, quem acionar). | **Central Operacional** com motor determinístico de regras por perfil, janelas de calendário/fuso, alerta de conflitos e busca local em base de conhecimento de procedimentos. |
| **Esquecimento de cobranças (follow-up), checklists de turno e passagens de plantão incompletas.** | Agenda de rotinas recorrentes com aviso de vencimento, linha do tempo por atendimento, auditoria de alertas recorrentes e geração automática de **Diário de Bordo**, **Passagem de Turno** e relatórios em **CSV/PDF**. |

---

## ✨ Principais Recursos

- **Importação direta do Zabbix (conexão de 10 horas):** coleta estruturada de alertas individuais ou em lote pela extensão do Microsoft Edge ou via JSON/Tampermonkey, incluindo captura automática da tabela de evidência e leitura de tags de solicitante e serviço.
- **Preenchimento assistido no Movidesk:** automação na sessão já autenticada do navegador do operador, com preservação da assinatura do agente (separada por uma linha em branco após o print) e captura automática do protocolo gerado.
- **Atendimento multicanal e fila com destaque visual:** busca instantânea, filtros por etapa e severidade (com cores para *Desastre*, *Alta*, *Média* e *Arquivado*), proteção de campos revisados manualmente, histórico de eventos e arquivamento.
- **Comunicação ágil em 1 clique:** botões rápidos de canal (`WhatsApp`, `Teams`, `E-mail`, ou atalhos `Alt+1`, `Alt+2`, `Alt+3`) com indicador `✓` de canal copiado, cópia rica de e-mail (`HTML` com `<br>` + texto puro + imagem) e popup na extensão para assinar mensagens no WhatsApp Web.
- **Destinatários por empresa com auto-seleção:** cadastro local de múltiplos e-mails em Para e Cc, pré-seleção automática da empresa pelo nome no Servidor/Alerta e cópia em 1 clique (`Copiar Para (N)` e `Copiar Cc (N)`).
- **Central Operacional integrada:** avaliação de regras por perfil, agenda de rotinas de turno, consulta a procedimentos locais, auditoria de recorrência e exportação de relatórios em PDF e CSV.
- **OCR local + IA sob demanda com proteção de dados:** fluxo principal 100% local e gratuito; integração opcional com **Groq** e **Google Gemini** (somente transcrição textual redigida e aprovada em prévia pelo operador; imagens nunca saem do computador).

---

## 🛠️ Tecnologias Utilizadas

- **Aplicativo Desktop e Interface:** Python 3.12 + Tkinter / TTK com execução assíncrona via `TarefasUI` e workers em threads.
- **OCR, Imagens e Clipboard:** WinRT (`Windows.Media.Ocr`), Pillow (PIL), Win32 Clipboard API (`CF_DIB`, `CF_UNICODETEXT` e `HTML Format` via `ctypes`) e `pyperclip`.
- **Integração com Navegador:** JavaScript (ES Modules), Microsoft Edge Extension (Manifest V3), Ponte HTTP Local (`127.0.0.1:18764`), `html2canvas` e Tampermonkey.
- **Persistência, Segurança e Relatórios:** Escrita atômica protegida por **Windows DPAPI** por usuário (`.noc_data/rascunho.json` e `.noc_data/credenciais.dpapi`), ReportLab (PDF) e CSV.
- **IA Opcional:** Groq SDK e Google Gemini SDK (`google-genai`) com validação estrita de JSON Schema, redação de dados sensíveis e confirmação de prévia.

---

## 🚀 Guia Rápido de Instalação e Uso

Você só precisa de um computador com **Windows 10 ou 11** e do navegador **Microsoft Edge**.

### Parte 1: Obter o Aplicativo

- **Opção A — Pasta pronta (`NOCFlow`):** extraia a pasta `NOCFlow` inteira (mantenha `NOCFlow.exe` junto da pasta `_internal`), crie um atalho para `NOCFlow.exe` na Área de Trabalho e abra o aplicativo.
- **Opção B — Código-fonte (GitHub):** instale o [Python 3.12 x64](https://www.python.org/downloads/) (marcando *"Add python.exe to PATH"*), baixe o repositório e dê dois cliques em **`scripts\Build Windows.cmd`**. Ele criará o executável em `dist\NOCFlow` e o atalho **`NOCFlow`** na sua Área de Trabalho.

### Parte 2: Configurar Domínios (`HTTPS`)

1. **Movidesk (`.env`):** no NOCFlow, abra **`⋯` > `Configurações`** e ajuste o endereço HTTPS do seu Movidesk:
   ```ini
   MOVIDESK_URL=https://suaempresa.movidesk.com
   NOME_OPERADOR=Seu Nome
   ```
   *(Opcional: para usar IA externa, preencha `GROQ_API_KEY` / `GEMINI_API_KEY` e defina `IA_EXTERNA_APROVADA=true`. Na primeira abertura, as chaves são migradas automaticamente para armazenamento seguro DPAPI).*
2. **Zabbix (`extensao.json`):** abra `%LOCALAPPDATA%\NOCFlow\.noc_data\extensao.json` (no executável) ou `.noc_data\extensao.json` (no código-fonte) e informe os domínios HTTPS do seu Zabbix:
   ```json
   {
     "zabbix_origens": [
       "https://zabbix.suaempresa.com.br"
     ]
   }
   ```
   Salve e reinicie o NOCFlow.

### Parte 3: Instalar a Extensão no Microsoft Edge

1. No NOCFlow, clique em **`⋯` > `Instalar extensão do Edge`**.
2. Clique em **`Copiar caminho`** e em **`Abrir extensões`** (`edge://extensions/`).
3. Ative o **`Modo do desenvolvedor`**, clique em **`Carregar sem compactação`** e cole o caminho copiado.

### Parte 4: Atender um Incidente

1. Clique em **`Conectar`** no topo do NOCFlow (a conexão dura **10 horas** e o indicador ficará verde: **`● Zabbix: conectado`**).
2. No Zabbix, abra o evento e clique em **`Enviar ao NOCFlow`** no painel inferior esquerdo.
3. No NOCFlow, revise os dados e clique em **`Criar ticket`**. Salve o chamado no Movidesk e o número retornará sozinho ao aplicativo.
4. Na aba **`Comunicar`**, clique no canal desejado (**`WhatsApp`**, **`Teams`** ou **`E-mail`**), copie os destinatários/assunto/mensagem e cole no destino.

---

## 🧪 Desenvolvimento e Validação

```powershell
python -m playwright install chromium --no-shell
$env:NOC_TEST_BROWSER = "1"
python -m unittest discover -s tests -v
python -m ruff check .
python scripts/verificar_build.py
.\build.ps1 -SomentePacote -PastaSaida dist
```
