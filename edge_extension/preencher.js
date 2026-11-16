// Executada no mundo MAIN pela extensão; os auxiliares precisam ficar nesta função.
export async function preencherFormulario(dados) {
  try {
    if (document.readyState !== "complete") {
      return {aguardar: true};
    }
    const normalizar = texto => String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();

    const assunto = document.querySelector('input#TicketSubject, input.subject:not([type="hidden"]), input[name="Subject"]:not([type="hidden"]), input[id*="Subject" i]:not([type="hidden"]), input[placeholder*="Assunto" i]:not([type="hidden"])') ||
      Array.from(document.querySelectorAll('input:not([type="hidden"])')).find(el => {
        const nome = (el.name || el.id || el.placeholder || "").toLowerCase();
        return /assunto|subject/.test(nome) && el.getClientRects().length;
      });

    const escopo = assunto?.closest("section.tab-ticket, form, .ticket-form, .container-ticket, body") || document;

    const jq = window.jQuery || window.$;
    const textarea = (escopo || document).querySelector('textarea.description, textarea[id*="desc" i], textarea[name*="desc" i]') || document.querySelector('textarea.description, textarea');
    const frElement = (escopo || document).querySelector('.container-text-editor .fr-element, .fr-view[contenteditable="true"], .fr-element[contenteditable="true"]') || document.querySelector('.fr-element[contenteditable="true"], .fr-view[contenteditable="true"]');
    const frame = (escopo || document).querySelector('iframe.tox-edit-area__iframe, iframe.k-content, iframe') || document.querySelector('iframe.tox-edit-area__iframe, iframe.k-content, iframe');
    const body = frame?.contentDocument?.body;
    let froala = (jq ? ((frElement ? jq(frElement).data("froala.editor") : null) || (textarea ? jq(textarea).data("froala.editor") : null)) : null) ||
      Array.from(window.FroalaEditor?.INSTANCES || []).find(editor => editor.el === frElement || editor.$el?.[0] === frElement);
    if (!froala && jq && frElement) {
      for (let el = frElement.parentElement; el && escopo.contains(el); el = el.parentElement) {
        const editor = jq(el).data("froala.editor");
        if (editor?.html?.set && editor?.image?.upload) { froala = editor; break; }
      }
    }
    const ce = frElement || (escopo || document).querySelector('[contenteditable="true"]');

    if (!assunto || !assunto.getClientRects().length || (!froala && !frElement && !body && !ce && !textarea)) {
      return {aguardar: true};
    }
    if (assunto.value.trim() && assunto.value !== dados.assunto) {
      throw new Error("O assunto já foi editado nesta guia. Revise o ticket antes de tentar novamente.");
    }
    const campos = {assunto: "pendente", descricao: "pendente", tipo: "nao_localizado", categoria: "nao_localizado", urgencia: "nao_localizado", tempo_apontado: "nao_localizado", atividade: "nao_localizado", solicitante: "nao_localizado", servico: "nao_localizado"};

  // 1. Assunto
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  if (setter) setter.call(assunto, dados.assunto);
  else assunto.value = dados.assunto;
  assunto.dispatchEvent(new Event("input", {bubbles: true}));
  assunto.dispatchEvent(new Event("change", {bubbles: true}));

  // 2. Tipo do ticket: selecionar "INTERNO"
      // Valores numéricos variam por layout: determine a opção pelo rótulo associado.
     function interno(seletor, seletorLabel) {
       const radios = Array.from(escopo.querySelectorAll(seletor));
       const label = escopo.querySelector(seletorLabel) || Array.from(escopo.querySelectorAll("label")).find(el => normalizar(el.textContent).replace(/^[✓✔?\s]+/, "") === (seletor.includes("ActionType") ? "acao interna" : "interno"));
       const alvoLabel = label?.control || label?.querySelector('input[type="radio"]');
       const radio = radios.find(el => el === alvoLabel ||
         Array.from(el.labels || []).some(l => /^intern[oa]$/.test(normalizar(l.textContent))) ||
         /^intern[oa]$/.test(normalizar(el.getAttribute("aria-label")))) ||
         (alvoLabel?.type === "radio" ? alvoLabel : null);
        if (radio) {
          if (!radio.checked) {
            const rotulo = Array.from(radio.labels || []).find(el => el.getClientRects().length);
            (rotulo || radio).click();
          }
         return radio;
       }
       if (label) label.click();
        return null;
      }
  try {
     const radioInterno = interno('input.ticketTypeOption, input[type="radio"][name="TicketType"]', 'label.TicketTypeLabel.internal, label.ticket-type-label.internal');
     const radioAcaoInterna = interno('input.actionTypeOption, input[type="radio"][name="ActionType"]', 'label.TicketActionTypeLabel.internal, label.labelInternal');
     const candidatos = Array.from((escopo || document).querySelectorAll("button, a, label, span, li, div[role='tab'], div[role='button']"));
    const btnInterno = candidatos.find(el => {
       const t = normalizar(el.textContent).replace(/^[✓✔?\s]+/, "");
      return t === "interno" && el.getClientRects().length;
    });
     if (!radioInterno && btnInterno && !btnInterno.classList.contains("active") && !btnInterno.classList.contains("selected") && btnInterno.getAttribute("aria-selected") !== "true") {
      btnInterno.click();
    }
    const radios = [radioInterno, radioAcaoInterna].filter(Boolean);
     if (radioInterno) campos.tipo = radios.every(el => el.checked) ? "preenchido" : "pendente";
     else if (btnInterno) campos.tipo = btnInterno.classList.contains("active") || btnInterno.classList.contains("selected") || btnInterno.getAttribute("aria-selected") === "true" || btnInterno.closest(".active, .selected") ? "preenchido" : "pendente";
     const acao = candidatos.find(el => normalizar(el.textContent) === "acao interna" && el.getClientRects().length);
     if (acao && !radioAcaoInterna) acao.click();
  } catch {}

  // 3. Funções para selecionar Categoria e Urgência
  function padroesUrgencia(severidade) {
    const s = normalizar(severidade);
    if (!s) return [];
    if (/(disaster|desastre|critica|urgente|altissima)/.test(s)) return [/^1\b/, /\bcritica\b/, /\burgente\b/, /\baltissima\b/, /\bdesastre\b/];
    if (/(high|alta)/.test(s)) return [/^2\b/, /\balta\b/];
    if (/(average|media|normal)/.test(s)) return [/^3\b/, /\bmedia\b/, /\bnormal\b/];
    if (/(warning|aviso|atencao|information|informacao|not classified|nao classificado|baixa)/.test(s)) return [/^4\b/, /\bbaixa\b/, /\baviso\b/, /\binformacao\b/];
    return [new RegExp(`\\b${s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`)];
  }

  function localizarCampos(seletor, rotulos) {
    const encontrados = new Set((escopo || document).querySelectorAll(seletor));
    for (const label of (escopo || document).querySelectorAll("label, .control-label, .field-label, span")) {
      const texto = normalizar(label.textContent).replace(/[:*]/g, "").trim();
      if (rotulos.includes(texto)) {
        if (label.htmlFor) {
          const alvo = document.getElementById(label.htmlFor);
          if (alvo) encontrados.add(alvo);
        }
        const grupo = label.closest(".form-group, .mv-field, .field, .k-widget, .mv-input-container, div");
        if (grupo) {
          for (const el of grupo.querySelectorAll("select, input")) encontrados.add(el);
        }
      }
    }
    return Array.from(encontrados);
  }

  function achatarArvore(itens) {
    return Array.from(itens || []).flatMap(item => item ? [item, ...achatarArvore(item.items)] : []);
  }

  function tecnologiaServico(tag) {
    const termo = normalizar(tag).replace(/^dba\s+/, "");
    const nomes = {sql: "SQL Server", "sql server": "SQL Server", sqlserver: "SQL Server", mssql: "SQL Server",
      mysql: "MySQL", oracle: "Oracle", postgres: "PostgreSQL", postgresql: "PostgreSQL",
      mongo: "MongoDB", mongodb: "MongoDB", redis: "Redis"};
    return nomes[termo] || String(tag || "").trim();
  }

  function selecaoVisivel(el) {
    const grupo = el.closest(".form-group, .mv-field, .mv-input-container, div");
    return Boolean(grupo && Array.from(grupo.querySelectorAll(".select2-search-choice, .select2-choice, .select2-selection__choice")).some(item => item.getClientRects().length));
  }

  async function selecionarSolicitante(elementos, codigo) {
    for (const el of elementos) {
      const s2 = jq ? jq(el).data("select2") : null;
      if (!s2?.opts?.ajax) continue;
      const atual = s2.data?.();
      if (atual && String(atual.id) === String(codigo)) return true;
      const ajax = s2.opts.ajax;
      const url = typeof ajax.url === "function" ? ajax.url() : ajax.url;
      const parametros = typeof ajax.data === "function" ? ajax.data(codigo, 1) : {q: codigo};
      let resposta;
      try {
        resposta = await new Promise((resolve, reject) => jq.ajax({url, type: ajax.type || "GET", dataType: "json",
          data: parametros, timeout: 8000, success: resolve, error: reject}));
      } catch { continue; }
      const processado = typeof ajax.results === "function" ? ajax.results(resposta) : resposta;
      const itens = Array.from(processado?.results || processado || []);
      // O código pertence ao contrato/organização; contatos individuais vêm com personType 1.
      const organizacoes = itens.filter(item => item && item.id && item.personType !== 1 && !item.email &&
        (item.personType === 4 || item.personType === 2 || (item.hierarchy || []).length === 2));
      const escolhido = organizacoes[0];
      if (!escolhido) {
        // Em formulários clonados o contrato já está selecionado e por isso é omitido da busca.
        if (selecaoVisivel(el)) return true;
        continue;
      }
      s2.data(escolhido);
      jq(el).trigger({type: "change", val: escolhido.id, added: escolhido});
      const depois = s2.data?.();
      if (depois && String(depois.id) === String(escolhido.id)) return true;
    }
    return false;
  }

  async function selecionarServico(elementos, tag) {
    const termo = tecnologiaServico(tag);
    for (const el of elementos) {
      const dadosWidget = jq ? jq(el).data() : {};
      if (typeof dadosWidget.setValue !== "function" || typeof dadosWidget.getOptions !== "function") continue;
      const atual = dadosWidget.getValue?.();
      if (atual && normalizar(atual.name) === normalizar(termo)) return true;
      const opts = dadosWidget.getOptions() || {};
      const parametros = {...(opts.urlParameters || {}), query: termo, ticketType: opts.ticketType, getAll: true};
      const atuais = dadosWidget.getItems?.()?.data || [];
      let indice = 0;
      for (const item of atuais) {
        if (!item.toDelete) parametros[`selecteds[${indice++}]`] = item.serviceId;
      }
      let resposta;
      try {
        resposta = await new Promise((resolve, reject) => jq.ajax({url: opts.searchUrl, type: opts.type || "GET",
          dataType: "json", data: parametros, timeout: 8000, success: resolve, error: reject}));
      } catch { continue; }
      const candidatos = achatarArvore(resposta).map(item => {
        let valor = {};
        try { valor = JSON.parse(item.value || "{}"); } catch {}
        return {...valor, _html: item.html || ""};
      }).filter(item => item.id && item.allowSelection !== false && !item.disabled && !/notActive/.test(item._html));
      const exatos = candidatos.filter(c => normalizar(c.name) === normalizar(termo));
      const alvo = exatos.find(c => normalizar(c.path) === "database") ||
        exatos.find(c => !/tempor/.test(normalizar(c.path))) || exatos[0] ||
        candidatos.find(c => normalizar(`${c.path || ""} ${c.name}`).includes(normalizar(termo)));
      if (!alvo) continue;
      dadosWidget.setValue({id: alvo.id, name: alvo.name, path: alvo.path || "", allowSelection: true,
        allowFinishTicket: alvo.allowFinishTicket !== false, serviceForTicketType: alvo.serviceForTicketType ?? 0,
        description: alvo.description ?? null, automationMacroId: alvo.automationMacroId ?? null});
      const escolhido = dadosWidget.getValue?.();
      if (escolhido && String(escolhido.id) === String(alvo.id)) return true;
    }
    return false;
  }

  async function selecionarCampo(elementos, padroes, busca = "", porCodigo = false) {
    const listar = itens => Array.from(itens || []).flatMap(item => item.children?.length ? listar(item.children) : [item]);
    const corresponde = item => {
      if (porCodigo) {
        // O código pesquisado pertence à organização/contrato, não ao contato retornado.
        const tipo = normalizar(item.type ?? item.Type ?? item.personType ?? "");
        if (item.email || item.Email || /contact|contato|person|pessoa/.test(tipo)) return false;
        if (!(item.isOrganization === true || /organization|organizacao|company|empresa|contract|contrato/.test(tipo))) return false;
      }
      return padroes.some(p => p.test(normalizar(porCodigo ? (item.code ?? item.Code ?? item.id ?? item.Id) : (item.text || item.name || ""))));
    };
    if (!padroes.length) return false;
    for (const el of elementos) {
      // Select2 (Movidesk nativo)
      if (jq) {
        const s2 = jq(el).data("select2");
        if (s2) {
          const atual = s2.data?.();
          if (atual && corresponde(atual)) {
            return true;
          }
           const estaticos = listar(Array.isArray(s2.opts?.data) ? s2.opts.data : s2.opts?.data?.results);
          if (Array.isArray(estaticos) && estaticos.length) {
            for (const p of padroes) {
              const opcoes = estaticos.filter(item => item && corresponde(item));
              const it = opcoes.length === 1 ? opcoes[0] : null;
              if (it) {
                s2.data(it);
                jq(el).trigger({type: "change", val: it.id, added: it});
                const escolhido = s2.data?.();
                return Boolean(escolhido && corresponde(escolhido));
              }
            }
          }
          const ajaxOpts = s2.opts?.ajax;
          if (ajaxOpts) {
            try {
              const url = typeof ajaxOpts.url === "function" ? ajaxOpts.url() : ajaxOpts.url;
              const dataParam = typeof ajaxOpts.data === "function" ? ajaxOpts.data(busca, 1) : {};
              const res = await new Promise((resolve, reject) => jq.ajax({
                url: url,
                type: ajaxOpts.type || "GET",
                dataType: "json",
                data: dataParam,
                timeout: 5000,
                success: resolve,
                error: reject
              }));
              const processado = typeof ajaxOpts.results === "function" ? ajaxOpts.results(res, 1) : res;
              const items = listar(processado?.results || (Array.isArray(processado) ? processado : []));
              for (const p of padroes) {
                const it = items.filter(item => item && item.id !== null && item.id !== undefined && corresponde(item));
                const unico = it.length === 1 ? it[0] : null;
                if (unico) {
                  s2.data(unico);
                  jq(el).trigger({type: "change", val: unico.id, added: unico});
                  const escolhido = s2.data?.();
                  return Boolean(escolhido && corresponde(escolhido));
                }
              }
            } catch {}
          }
        }
      }

      // Kendo DropDownList / ComboBox
      const widget = jq ? (jq(el).data("kendoDropDownList") || jq(el).data("kendoComboBox")) : null;
      if (widget) {
        const itens = Array.from(widget.dataSource?.data?.() || []);
        const campoTexto = widget.options?.dataTextField || "Name";
        const campoValor = widget.options?.dataValueField || "Id";
        for (const padrao of padroes) {
          const indice = itens.findIndex(item => {
            const texto = normalizar(item?.[campoTexto] ?? item?.Name ?? item?.Text ?? item?.text ?? item?.Description ?? item);
            return padrao.test(texto);
          });
          if (indice >= 0) {
            const item = itens[indice];
            const valor = item?.[campoValor] ?? item?.Id ?? item?.Value ?? item?.value;
            if (valor !== undefined && typeof widget.value === "function") widget.value(valor);
            if (typeof widget.select === "function") widget.select(indice);
            if (typeof widget.trigger === "function") widget.trigger("change");
            return typeof widget.value === "function" && String(widget.value()) === String(valor);
          }
        }
        if (!itens.length && typeof widget.bind === "function" && !el.dataset.nocflowBound) {
          el.dataset.nocflowBound = "1";
          widget.bind("dataBound", () => selecionarCampo([el], padroes));
        }
      }

      // Select nativo
      if (el.tagName === "SELECT" && el.options?.length) {
        const opcoes = Array.from(el.options);
        for (const padrao of padroes) {
           const opcao = opcoes.find(o => padrao.test(normalizar(porCodigo ? o.value : (o.textContent || o.text || o.value))));
          if (opcao) {
            el.value = opcao.value;
            el.dispatchEvent(new Event("input", {bubbles: true}));
            el.dispatchEvent(new Event("change", {bubbles: true}));
            return el.value === opcao.value && opcao.selected;
          }
        }
      }
    }
    return false;
  }

  try {
    const padroesCat = [new RegExp(`\\b${normalizar(dados.categoria || "Alerta")}\\b`)];
    const padroesUrg = padroesUrgencia(dados.severidade);
    const categorias = localizarCampos('select[name*="Category" i], input[name*="Category" i], select[id*="Category" i], input[id*="Category" i], select[name*="Categoria" i], input[name*="Categoria" i], select[id*="Categoria" i], input[id*="Categoria" i], input.category', ["categoria", "category"]);
    const urgencias = localizarCampos('select[name*="Urgency" i], input[name*="Urgency" i], select[id*="Urgency" i], input[id*="Urgency" i], select[name*="Urgencia" i], input[name*="Urgencia" i], select[id*="Urgencia" i], input[id*="Urgencia" i], select[name*="Severity" i], select[id*="Severity" i], input.urgency', ["urgencia", "urgency", "severidade"]);
    if (categorias.length) campos.categoria = "pendente";
    if (urgencias.length) campos.urgencia = "pendente";
    if (await selecionarCampo(categorias, padroesCat)) campos.categoria = "preenchido";
    if (await selecionarCampo(urgencias, padroesUrg)) campos.urgencia = "preenchido";
  } catch {}

  const emSecaoVisivel = el => {
    const secao = el.closest("section");
    return !secao || secao.getClientRects().length > 0;
  };
  try {
    if (dados.solicitante) {
      const alvos = localizarCampos('input.clients, input.requester, input.client, input[name*="Client" i], select[name*="Requester" i]', ["solicitante", "cliente"]).filter(emSecaoVisivel);
      campos.solicitante = alvos.length ? "pendente" : "nao_localizado";
      if (await selecionarSolicitante(alvos, String(dados.solicitante).split(/[,;]/)[0].trim())) campos.solicitante = "preenchido";
    }
    if (dados.servico) {
      const alvos = localizarCampos('input.service, input[name*="Service" i], select[name*="Service" i]', ["servico"]).filter(emSecaoVisivel);
      campos.servico = alvos.length ? "pendente" : "nao_localizado";
      if (await selecionarServico(alvos, String(dados.servico).trim())) campos.servico = "preenchido";
    }
  } catch {}

  // Apontamento inicial: apenas campos da linha de horas, nunca o tempo contabilizado.
  function camposHoras() {
    const tempos = localizarCampos('input[name*="TimeSpent" i], input[id*="TimeSpent" i], input[name*="TempoApontado" i], input[id*="TempoApontado" i]', ["tempo apontado"]);
    const atividades = localizarCampos('select[name*="Activity" i], input[name*="Activity" i], select[id*="Activity" i], input[id*="Activity" i]', ["atividade"]);
    for (const tabela of escopo.querySelectorAll("table")) {
      const cabecalhos = Array.from(tabela.querySelectorAll("thead th, thead td"));
      cabecalhos.forEach((th, indice) => {
        const destino = normalizar(th.textContent) === "tempo apontado" ? tempos : normalizar(th.textContent) === "atividade" ? atividades : null;
        if (!destino) return;
        const linha = Array.from(tabela.querySelectorAll("tbody tr")).find(tr => tr.getClientRects().length && tr.cells[indice]?.querySelector("input, select"));
        if (linha) destino.push(...linha.cells[indice].querySelectorAll("input, select"));
      });
    }
    return {tempos: [...new Set(tempos)].filter(el => el.tagName === "INPUT" && el.type !== "hidden" && !el.disabled && !el.readOnly && el.getClientRects().length), atividades: [...new Set(atividades)]};
  }
  try {
    let horas = camposHoras();
    if (!horas.tempos.length) {
      const abrirHoras = Array.from(escopo.querySelectorAll("button, a, [role='button']")).find(el =>
        /^(apontar horas|apontamento de horas|adicionar apontamento|registrar tempo)$/.test(normalizar(el.getAttribute("title") || el.getAttribute("aria-label") || el.textContent)) && el.getClientRects().length);
      if (abrirHoras) {
        abrirHoras.click();
        for (let tentativa = 0; tentativa < 10 && !horas.tempos.length; tentativa++) {
          await new Promise(resolve => setTimeout(resolve, 100));
          horas = camposHoras();
        }
      }
    }
    const linhaHoras = horas.tempos[0]?.closest("tr");
    if (linhaHoras) horas.atividades = horas.atividades.filter(el => linhaHoras.contains(el));
    if (horas.atividades.length) {
      campos.atividade = "pendente";
      if (await selecionarCampo(horas.atividades, [/^observability$/])) campos.atividade = "preenchido";
    }
    if (horas.tempos.length) {
      campos.tempo_apontado = "pendente";
      // Não substitui tempo já informado pelo operador, nem cria linhas duplicadas.
      const tempo = horas.tempos[0];
      if (!tempo.value.trim() || /^(00:00|0:00|0)$/.test(tempo.value.trim())) {
        setter.call(tempo, "00:03");
        tempo.dispatchEvent(new Event("input", {bubbles: true}));
        tempo.dispatchEvent(new Event("change", {bubbles: true}));
      }
      if (tempo.value === "00:03") campos.tempo_apontado = "preenchido";
    }
  } catch {}

  // 4. Editor de Texto Rico (Froala / TinyMCE / Kendo / iframe)
  let htmlAtual = "";
  if (froala && typeof froala.html?.get === "function") {
    htmlAtual = froala.html.get() || "";
  } else if (frElement) {
    htmlAtual = frElement.innerHTML || "";
  } else if (body) {
    htmlAtual = body.innerHTML || "";
  } else if (ce) {
    htmlAtual = ce.innerHTML || "";
  } else if (textarea) {
    htmlAtual = textarea.value || "";
  }

  let htmlFinal = "";
  const conteudoAtual = document.createElement("div");
  conteudoAtual.innerHTML = htmlAtual;
  const jaPreenchido = Boolean(conteudoAtual.querySelector('[data-nocflow-conteudo="1"]'));
  const bloco = `<div data-nocflow-conteudo="1">${dados.html}</div>`;
  const evidencia = document.createElement("div");
  evidencia.innerHTML = bloco;
  const imagensUpload = Array.from(evidencia.querySelectorAll('img[src^="data:image/"]'));
  const arquivos = [];
  if (!jaPreenchido && imagensUpload.length) {
    if (!froala?.image?.upload) throw new Error("Editor sem upload de imagem disponível. Anexe o print pelo Movidesk; a imagem base64 não será inserida pois pode quebrar ao salvar.");
    for (const img of imagensUpload) {
      const blob = await (await fetch(img.src)).blob();
      arquivos.push(new File([blob], "alerta.png", {type: blob.type}));
      img.remove();
    }
  }

  if (jaPreenchido) {
    htmlFinal = htmlAtual;
  } else if (htmlAtual.trim()) {
    htmlFinal = `${evidencia.innerHTML}<p><br></p>${htmlAtual}`;
  } else {
    htmlFinal = evidencia.innerHTML;
  }

  let preenchido = false;
  if (froala && typeof froala.html?.set === "function") {
    froala.html.set(htmlFinal);
    if (textarea) textarea.value = htmlFinal;
    try { froala.events?.trigger?.("contentChanged"); } catch {}
    try { froala.undo?.saveStep?.(); } catch {}
    preenchido = true;
  }
  if (frElement && !preenchido) {
    frElement.focus();
    frElement.innerHTML = htmlFinal;
    frElement.dispatchEvent(new Event("input", {bubbles: true}));
    frElement.dispatchEvent(new Event("change", {bubbles: true}));
    frElement.blur();
    if (textarea) textarea.value = htmlFinal;
    preenchido = true;
  }
  const editores = window.tinymce?.get?.() || window.tinymce?.editors || [];
  const tiny = Array.from(editores).find(editor => editor.iframeElement === frame || editor.getBody?.() === body);
  if (tiny) {
    tiny.setContent(htmlFinal);
    tiny.setDirty(true);
    tiny.save();
    tiny.fire("input");
    tiny.fire("change");
    preenchido = true;
  } else if (jq) {
    jq('[data-role="editor"]').each(function () {
      const editor = jq(this).data("kendoEditor");
      if (editor && (editor.body === body || editor.element?.[0] === textarea)) {
        editor.value(htmlFinal);
        editor.trigger("change");
        preenchido = true;
      }
    });
  }
  if (body && !preenchido) {
    body.focus();
    body.innerHTML = htmlFinal;
    body.dispatchEvent(new Event("input", {bubbles: true}));
    body.dispatchEvent(new Event("change", {bubbles: true}));
    body.blur();
    preenchido = true;
  }
  if (!preenchido && ce) {
    ce.innerHTML = htmlFinal;
    ce.dispatchEvent(new Event("input", {bubbles: true}));
    ce.dispatchEvent(new Event("change", {bubbles: true}));
    preenchido = true;
  }
  if (!preenchido && textarea) {
    textarea.value = htmlFinal;
    textarea.dispatchEvent(new Event("input", {bubbles: true}));
    textarea.dispatchEvent(new Event("change", {bubbles: true}));
    preenchido = true;
  }

   if (arquivos.length) {
     const antes = document.createElement("div");
     antes.innerHTML = froala.html.get();
     const fontesAnteriores = new Set(Array.from(antes.querySelectorAll("img")).map(img => img.getAttribute("src")));
     const imagemNova = img => {
       const src = img.getAttribute("src");
       return Boolean(src && !fontesAnteriores.has(src) && /^https?:/i.test(new URL(src, location.href).href));
     };
     const acharLink = doc => {
       const links = Array.from(doc.querySelectorAll("a[href]"));
       let esperado = "";
       try { esperado = dados.link_zabbix ? new URL(dados.link_zabbix, location.href).href : ""; } catch {}
       return links.find(a => esperado && (a.href === esperado || a.getAttribute("href") === dados.link_zabbix)) ||
         links.find(a => /tr_events\.php/i.test(a.getAttribute("href") || "")) ||
         links[0] ||
         doc.querySelector('[data-nocflow-alerta="1"], [data-nocflow-conteudo="1"]');
     };
     const novasImagens = doc => Array.from(doc.querySelectorAll("img")).filter(imagemNova);
     // O print deve ficar logo abaixo do link, nunca depois da assinatura.
     const abaixoDoLink = doc => {
       const link = acharLink(doc);
       const novas = novasImagens(doc);
       if (!link || !novas.length) return false;
       const img = novas[0];
       const bloco = link.closest('[data-nocflow-alerta="1"], [data-nocflow-conteudo="1"]');
       if (bloco) {
         const pLink = link.closest("p");
         if (pLink && img.closest("p") === pLink) return false;
         return bloco.contains(img) && Boolean(link.compareDocumentPosition(img) & Node.DOCUMENT_POSITION_FOLLOWING);
       }
       const referencia = link.closest("p") || link;
       let seguinte = referencia.nextElementSibling;
       while (seguinte && !seguinte.textContent.trim() && !seguinte.querySelector("img")) seguinte = seguinte.nextElementSibling;
       return Boolean(seguinte && seguinte.contains(img));
     };
     froala.events?.focus?.();
     const blocoEditor = froala.el?.querySelector('[data-nocflow-conteudo="1"]');
     froala.selection?.setAtEnd?.(blocoEditor || froala.el);
     froala.image.upload(arquivos);
     let posicionado = false;
     let viuImagem = false;
     for (let tentativa = 0; tentativa < 20; tentativa++) {
       await new Promise(resolve => setTimeout(resolve, 200));
       const corpo = document.createElement("div");
       corpo.innerHTML = froala.html.get();
       const novas = novasImagens(corpo);
       viuImagem = viuImagem || novas.length > 0;
       const link = acharLink(corpo);
       if (novas.length && link && abaixoDoLink(corpo)) {
         posicionado = true;
         break;
       }
       if (!novas.length || !link) continue;
       const referencia = link.closest("p") || link;
       const bloco = link.closest('[data-nocflow-alerta="1"], [data-nocflow-conteudo="1"]');
       const caixa = document.createElement("p");
       caixa.setAttribute("data-nocflow-print", "1");
       caixa.style.margin = "0";
       for (const img of novas) caixa.append(img);
       if (bloco && referencia === bloco) {
         const alvo = Array.from(bloco.children).find(item => item.contains(link)) || link;
         alvo.after(caixa);
       } else {
         referencia.after(caixa);
       }
       froala.html.set(corpo.innerHTML);
       if (textarea) textarea.value = corpo.innerHTML;
       try { froala.events?.trigger?.("contentChanged"); } catch {}
     }
     if (!posicionado) {
       throw new Error(viuImagem
         ? "O Movidesk não confirmou o print abaixo do link. Revise o corpo antes de salvar."
         : "Upload do print não confirmado pelo Movidesk. Revise o anexo antes de salvar.");
     }
   }
   const htmlCorpo = (froala ? froala.html?.get?.() : "") || frElement?.innerHTML || body?.innerHTML || ce?.innerHTML || textarea?.value || "";
   const recebido = document.createElement("div"), esperado = document.createElement("div");
   recebido.innerHTML = htmlCorpo;
   esperado.innerHTML = dados.html;
   const texto = el => el.textContent.replace(/\s+/g, " ").trim();
   const imagens = Array.from(recebido.querySelectorAll("img")).map(img => img.getAttribute("src"));
   const confirmouCorpo = preenchido && texto(recebido).includes(texto(esperado)) &&
      Array.from(esperado.querySelectorAll("img")).every(img => arquivos.length ? imagens.some(src => src && !/^(data:|blob:)/.test(src)) : imagens.includes(img.getAttribute("src")));

  if (!confirmouCorpo || assunto.value !== dados.assunto) {
    throw new Error("O formulário não confirmou o preenchimento. Revise a guia aberta.");
  }
   campos.assunto = "preenchido";
   campos.descricao = "preenchido";
   const confirmarTipo = interno('input.ticketTypeOption, input[type="radio"][name="TicketType"]', 'label.TicketTypeLabel.internal, label.ticket-type-label.internal');
   if (confirmarTipo) campos.tipo = confirmarTipo.checked ? "preenchido" : "pendente";
   if (dados.exigir_interno && campos.tipo !== "preenchido") {
     throw new Error("Não foi possível confirmar o tipo Interno. Selecione INTERNO antes de salvar o ticket.");
   }
   return {ok: true, campos};
} catch (err) {
  return {erro: err.message || String(err)};
}
}
