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
    const froala = jq ? ((frElement ? jq(frElement).data("froala.editor") : null) || (textarea ? jq(textarea).data("froala.editor") : null)) : null;
    const ce = frElement || (escopo || document).querySelector('[contenteditable="true"]');

    if (!assunto || !assunto.getClientRects().length || (!froala && !frElement && !body && !ce && !textarea)) {
      return {aguardar: true};
    }
    if (assunto.value.trim() && assunto.value !== dados.assunto) {
      throw new Error("O assunto já foi editado nesta guia. Revise o ticket antes de tentar novamente.");
    }
    const campos = {assunto: "pendente", descricao: "pendente", tipo: "nao_localizado", categoria: "nao_localizado", urgencia: "nao_localizado", tempo_apontado: "nao_localizado", atividade: "nao_localizado"};

  // 1. Assunto
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  if (setter) setter.call(assunto, dados.assunto);
  else assunto.value = dados.assunto;
  assunto.dispatchEvent(new Event("input", {bubbles: true}));
  assunto.dispatchEvent(new Event("change", {bubbles: true}));

  // 2. Tipo do ticket: selecionar "INTERNO"
  try {
     // Valores numéricos variam por layout: determine a opção pelo rótulo associado.
     function interno(seletor, seletorLabel) {
       const radios = Array.from(escopo.querySelectorAll(seletor));
       const label = escopo.querySelector(seletorLabel);
       const alvoLabel = label?.control || label?.querySelector('input[type="radio"]');
       const radio = radios.find(el => el === alvoLabel ||
         Array.from(el.labels || []).some(l => /^intern[oa]$/.test(normalizar(l.textContent))) ||
         /^intern[oa]$/.test(normalizar(el.getAttribute("aria-label")))) ||
         (alvoLabel?.type === "radio" ? alvoLabel : null);
       if (radio) {
         if (!radio.checked) radio.click();
         return radio;
       }
       if (label) label.click();
       return null;
     }
     const radioInterno = interno('input.ticketTypeOption, input[type="radio"][name="TicketType"]', 'label.TicketTypeLabel.internal, label.ticket-type-label.internal');
     const radioAcaoInterna = interno('input.actionTypeOption, input[type="radio"][name="ActionType"]', 'label.TicketActionTypeLabel.internal, label.labelInternal');
    const candidatos = Array.from((escopo || document).querySelectorAll("button, a, label, span, li, div[role='tab'], div[role='button']"));
    const btnInterno = candidatos.find(el => {
      const t = normalizar(el.textContent).replace(/^✓\s*/, "");
      return t === "interno" && el.getClientRects().length;
    });
     if (!radioInterno && btnInterno && !btnInterno.classList.contains("active") && !btnInterno.classList.contains("selected") && btnInterno.getAttribute("aria-selected") !== "true") {
      btnInterno.click();
    }
    const radios = [radioInterno, radioAcaoInterna].filter(Boolean);
     if (radioInterno) campos.tipo = radios.every(el => el.checked) ? "preenchido" : "pendente";
    else if (btnInterno) campos.tipo = btnInterno.classList.contains("active") || btnInterno.classList.contains("selected") || btnInterno.getAttribute("aria-selected") === "true" ? "preenchido" : "pendente";
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

  async function selecionarCampo(elementos, padroes) {
    if (!padroes.length) return false;
    for (const el of elementos) {
      // Select2 (Movidesk nativo)
      if (jq) {
        const s2 = jq(el).data("select2");
        if (s2) {
          const atual = s2.data?.();
          if (atual && padroes.some(p => p.test(normalizar(atual.text || atual.name || "")))) {
            return true;
          }
          const estaticos = s2.opts?.data || [];
          if (Array.isArray(estaticos) && estaticos.length) {
            for (const p of padroes) {
              const it = estaticos.find(item => item && p.test(normalizar(item.text || item.name || "")));
              if (it) {
                s2.data(it);
                jq(el).trigger({type: "change", val: it.id, added: it});
                el.dispatchEvent(new Event("change", {bubbles: true}));
                const escolhido = s2.data?.();
                return Boolean(escolhido && padroes.some(p => p.test(normalizar(escolhido.text || escolhido.name))));
              }
            }
          }
          const ajaxOpts = s2.opts?.ajax;
          if (ajaxOpts) {
            try {
              const url = typeof ajaxOpts.url === "function" ? ajaxOpts.url() : ajaxOpts.url;
              const dataParam = typeof ajaxOpts.data === "function" ? ajaxOpts.data("", 1) : {};
              const res = await new Promise((resolve, reject) => jq.ajax({
                url: url,
                type: ajaxOpts.type || "GET",
                dataType: "json",
                data: dataParam,
                timeout: 5000,
                success: resolve,
                error: reject
              }));
              const items = res?.results || (Array.isArray(res) ? res : []);
              for (const p of padroes) {
                const it = items.find(item => item && item.id !== null && item.id !== undefined && p.test(normalizar(item.text || item.name || "")));
                if (it) {
                  s2.data(it);
                  jq(el).trigger({type: "change", val: it.id, added: it});
                  el.dispatchEvent(new Event("change", {bubbles: true}));
                  const escolhido = s2.data?.();
                  return Boolean(escolhido && padroes.some(p => p.test(normalizar(escolhido.text || escolhido.name))));
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
          const opcao = opcoes.find(o => padrao.test(normalizar(o.textContent || o.text || o.value)));
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
    if (horas.tempos.length) {
      campos.tempo_apontado = "pendente";
      // Não substitui tempo já informado pelo operador, nem cria linhas duplicadas.
      const tempo = horas.tempos[0];
      if (!tempo.value.trim() || /^(00:00|0:00|0)$/.test(tempo.value.trim())) {
        setter.call(tempo, "00:03");
        tempo.dispatchEvent(new Event("input", {bubbles: true}));
        tempo.dispatchEvent(new Event("change", {bubbles: true}));
        tempo.dispatchEvent(new Event("blur", {bubbles: true}));
      }
      if (tempo.value === "00:03") campos.tempo_apontado = "preenchido";
    }
    if (horas.atividades.length) {
      campos.atividade = "pendente";
      if (await selecionarCampo(horas.atividades, [/^observability$/])) campos.atividade = "preenchido";
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

  if (jaPreenchido) {
    htmlFinal = htmlAtual;
  } else if (htmlAtual.trim()) {
    htmlFinal = `${bloco}<p><br></p>${htmlAtual}`;
  } else {
    htmlFinal = bloco;
  }

  let preenchido = false;
  if (froala && typeof froala.html?.set === "function") {
    froala.html.set(htmlFinal);
    if (textarea) textarea.value = htmlFinal;
    try { froala.events?.trigger?.("contentChanged"); } catch {}
    try { froala.undo?.saveStep?.(); } catch {}
    preenchido = true;
  }
  if (frElement) {
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
  if (body) {
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

   const htmlCorpo = (froala ? froala.html?.get?.() : "") || frElement?.innerHTML || body?.innerHTML || ce?.innerHTML || textarea?.value || "";
   const recebido = document.createElement("div"), esperado = document.createElement("div");
   recebido.innerHTML = htmlCorpo;
   esperado.innerHTML = dados.html;
   const texto = el => el.textContent.replace(/\s+/g, " ").trim();
   const imagens = Array.from(recebido.querySelectorAll("img")).map(img => img.getAttribute("src"));
   const confirmouCorpo = preenchido && texto(recebido).includes(texto(esperado)) &&
     Array.from(esperado.querySelectorAll("img")).every(img => imagens.includes(img.getAttribute("src")));

  if (!confirmouCorpo || assunto.value !== dados.assunto) {
    throw new Error("O formulário não confirmou o preenchimento. Revise a guia aberta.");
  }
   campos.assunto = "preenchido";
   campos.descricao = "preenchido";
   return {ok: true, campos};
} catch (err) {
  return {erro: err.message || String(err)};
}
}
