# Histórico de versões

## [2.3.0]

### Adicionado
- Cadastro de empresas e destinatários Para/Cc com auto-seleção pelo Servidor/Alerta e cópia separada das listas.
- Seletor rápido de canal em 1 clique (`WhatsApp`, `Teams`, `E-mail`) com indicador `✓` de cópia e atalhos `Alt+1`, `Alt+2` e `Alt+3`.
- Controles rápidos de anexo (`Print completo` / `Recorte` e botão `Recortar`) no rodapé da aba Comunicar e botão `Abrir ↗` no Link Zabbix.
- Destaques visuais por severidade na Fila e por atraso na Central Operacional, além do botão `Limpar filtros`.
- Proteção DPAPI para rascunhos e credenciais, bloqueio padrão de IA externa com redação e janela de confirmação de prévia, e migração para o SDK `google-genai`.
- CI Windows com testes, Ruff, OCR, build, SBOM/proveniência e smoke do executável.
- Dependabot semanal, auditoria de vulnerabilidades com `pip-audit` e release por tag com ZIP e SHA-256.

### Corrigido
- Preservação rigorosa das quebras de linha (`<br>` em HTML + `\r\n` em texto puro) ao copiar e colar comunicados de e-mail com ou sem imagem.
- Inserção de exatamente 1 quebra de linha entre a foto do Zabbix e a assinatura do operador ao preencher tickets no Movidesk.
- Seleção e confirmação do tipo Interno antes de localizar e preencher o editor do Movidesk.
- Atualizadas Pillow, certifi, pyasn1, cryptography e setuptools para versões sem vulnerabilidades conhecidas no `pip-audit`.
- Exportação JSON do Zabbix pelo Tampermonkey.

### Melhorado
- Tempo de sessão da conexão com o Zabbix ajustado para 10 horas.
- Processamento assíncrono de imagens, exportações e tarefas locais (`TarefasUI`).
- Simplificação e atualização completa da documentação (`README.md`, `docs/manual.md` e `docs/arquitetura.md`).
