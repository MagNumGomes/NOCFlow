# Histórico de versões

## [2.3.0]

### Adicionado
- Cadastro de empresas e destinatários Para/Cc com cópia separada das listas.
- CI Windows com testes, Ruff, OCR, build e smoke do executável.
- Dependabot semanal e auditoria de vulnerabilidades com pip-audit.
- Versão centralizada, snapshot de dependências e release por tag com ZIP e SHA-256.

### Corrigido
- Atualizadas Pillow, certifi, pyasn1 e setuptools para versões sem os alertas conhecidos encontrados pelo pip-audit.
- Seleção e confirmação do tipo Interno antes de preencher o ticket.
- Espaçamento entre evidência e assinatura no Movidesk.
- Exportação JSON do Zabbix pelo Tampermonkey.

### Melhorado
- Processamento assíncrono de imagens, exportações e tarefas locais.
- Modularização incremental, persistência atômica, limites da ponte HTTP e logs JSONL.

### Limitações conhecidas
- Execução por fonte requer Python 3.11 ou superior após a atualização de segurança do Pillow; o ambiente homologado usa Python 3.12 x64. O executável já inclui o Python.
- SDK Gemini legado ainda requer migração para google.genai.
- A automação DOM deve ser homologada nas instâncias reais de Zabbix/Movidesk.
