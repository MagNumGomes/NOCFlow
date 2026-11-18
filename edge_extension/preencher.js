// Executada no mundo MAIN pela extensão; os auxiliares precisam ficar nesta função.
export async function preencherFormulario(dados) {
  try {
    if (document.readyState !== "complete") {
      return {aguardar: true};
    }
    const normalizar = texto => String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
    const seletores = {
      formulario: "section.tab-ticket.ticket.active, .tab-pane.active, form.ticket-form, .container-ticket",
      assunto: 'input#TicketSubject, input.subject:not([type="hidden"]), input[name="Subject"]:not([type="hidden"]), input[id*="Subject" i]:not([type="hidden"]), input[placeholder*="Assunto" i]:not([type="hidden"])',
      descricao: 'textarea.description, textarea[id*="desc" i], textarea[name*="desc" i]',
      rico: '.container-text-editor .fr-element, .fr-view[contenteditable="true"], .fr-element[contenteditable="true"]',
      frame: 'iframe.tox-edit-area__iframe, iframe.k-content',
      servico: 'input.service, input[name*="Service" i], select[name*="Service" i]'
    };
    const visivel = el => Boolean(el.getClientRects().length) && getComputedStyle(el).visibility !== "hidden";
    const formularios = Array.from(document.querySelectorAll(seletores.formulario)).filter(visivel);
    const raiz = formularios.length === 1 ? formularios[0] : document;
    const assuntos = Array.from(raiz.querySelectorAll(seletores.assunto)).filter(visivel);
    if (assuntos.length > 1) return {erro: "Mais de um formulário visível. Ative somente o ticket que deseja preencher."};

    const assunto = assuntos[0];

    const escopo = assunto?.closest("section.tab-ticket, form, .ticket-form, .container-ticket, body") || document;

    const jq = window.jQuery || window.$;
    const unico = seletor => {
      const elementos = Array.from(escopo.querySelectorAll(seletor));
      return elementos.length === 1 ? elementos[0] : null;
    };
    const nomeTipo = el => normalizar(el.textContent || el.getAttribute("aria-label")).replace(/^[✓✔\s]+/, "");
    function controleInterno() {
      const rotulos = Array.from(escopo.querySelectorAll('label, button, a, [role="tab"], [role="radio"]'))
        .filter(el => visivel(el) && nomeTipo(el) === "interno");
      const radios = Array.from(escopo.querySelectorAll('input.ticketTypeOption, input[type="radio"][name="TicketType"]'));
      const radio = radios.find(el => Array.from(el.labels || []).some(l => nomeTipo(l) === "interno") ||
        normalizar(el.getAttribute("aria-label")) === "interno");
      const rotulo = rotulos.find(el => el.control === radio) || (rotulos.length === 1 ? rotulos[0] : null);
      return {radio: radio || rotulo?.control, rotulo};
    }
    function tipoConfirmado() {
      const {radio, rotulo} = controleInterno();
      if (radio?.type === "radio") return radio.checked;
      if (!rotulo) return false;
      return rotulo.matches('.active, .selected, [aria-selected="true"], [aria-checked="true"]') ||
        Boolean(rotulo.querySelector('input:checked, .fa-check, .glyphicon-ok, .icon-check')) ||
        /^[\s]*[✓✔]/.test(rotulo.textContent);
    }
    // O tipo deve mudar antes de localizar o editor: o Movidesk pode recriá-lo.
    const tipoInicial = controleInterno();
    if (!tipoConfirmado() && (tipoInicial.radio || tipoInicial.rotulo)) {
      (tipoInicial.rotulo || tipoInicial.radio).click();
      for (let i = 0; i < 20; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        if (tipoConfirmado()) break;
      }
    }
    if (dados.exigir_interno && !tipoConfirmado()) {
      throw new Error("Não foi possível selecionar o tipo Interno. Selecione INTERNO antes de preencher o ticket.");
    }
    const textarea = unico(seletores.descricao) || unico("textarea");
    const frElement = unico(seletores.rico);
    const frame = unico(seletores.frame);
    let body;
    try { body = frame?.contentDocument?.body; } catch { body = null; }
    let froala = (jq ? ((frElement ? jq(frElement).data("froala.editor") : null) || (textarea ? jq(textarea).data("froala.editor") : null)) : null) ||
      Array.from(window.FroalaEditor?.INSTANCES || []).find(editor => editor.el === frElement || editor.$el?.[0] === frElement);
    if (!froala && jq && frElement) {
      for (let el = frElement.parentElement; el && escopo.contains(el); el = el.parentElement) {
        const editor = jq(el).data("froala.editor");
        if (editor?.html?.set && editor?.image?.upload) { froala = editor; break; }
      }
    }
    const ce = frElement || unico('[contenteditable="true"]');

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

   campos.tipo = tipoConfirmado() ? "preenchido" : (tipoInicial.radio || tipoInicial.rotulo ? "pendente" : "nao_localizado");

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
      mysql: "MySQL", oracle: "Oracle", postgre: "PostgreSQL", postgres: "PostgreSQL", postgresql: "PostgreSQL",
      mongo: "MongoDB", mongodb: "MongoDB", redis: "Redis"};
    return nomes[termo] || String(tag || "").trim();
  }

  function resolverServico(dados) {
    if (dados.servico && String(dados.servico).trim()) {
      return tecnologiaServico(dados.servico);
    }
    const especificos = new Set();
    for (const linha of String(dados.tags || "").split("\n")) {
      if (!linha.includes(":")) continue;
      const chave = normalizar(linha.split(":")[0]);
      if (chave === "movidesk") continue;
      const valor = linha.slice(linha.indexOf(":") + 1).trim();
      const convertido = tecnologiaServico(valor);
      if (["SQL Server", "MySQL", "Oracle", "PostgreSQL", "MongoDB", "Redis"].includes(convertido)) {
        especificos.add(convertido);
      }
    }
    if (especificos.size === 1) return [...especificos][0];
    if (especificos.size > 1) {
      const textoContexto = normalizar(`${dados.alerta || ""} ${dados.servidor || ""}`);
      const pistas = [
        ["SQL Server", /\b(?:mssql|sql\s*server|sqlserver)\b/],
        ["MySQL", /\b(?:mysql|mariadb)\b/],
        ["PostgreSQL", /\b(?:postgre|postgres|postgresql)\b/],
        ["MongoDB", /\b(?:mongo|mongodb)\b/],
        ["Oracle", /\boracle\b/],
        ["Redis", /\bredis\b/]
      ];
      const correspondentes = pistas.filter(([nome, regex]) => especificos.has(nome) && regex.test(textoContexto));
      if (correspondentes.length === 1) return correspondentes[0][0];
      if (/\bsql\b/.test(textoContexto) && !/\b(?:mysql|postgre|postgres)\b/.test(textoContexto) && especificos.has("SQL Server")) {
        return "SQL Server";
      }
    }
    return "";
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
       const exatas = organizacoes.filter(item => String(item.code ?? item.Code ?? item.id) === String(codigo));
       const escolhido = exatas.length === 1 ? exatas[0] : organizacoes.length === 1 ? organizacoes[0] : null;
      if (!escolhido) {
        // Em formulários clonados o contrato já está selecionado e por isso é omitido da busca.
         if (atual && String(atual.code ?? atual.Code ?? atual.id) === String(codigo)) return true;
        continue;
      }
      s2.data(escolhido);
      jq(el).trigger({type: "change", val: escolhido.id, added: escolhido});
      const depois = s2.data?.();
      if (depois && String(depois.id) === String(escolhido.id)) {
        for (let espera = 0; espera < 15 && Number(jq.active || 0) > 0; espera++) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        return true;
      }
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
       const preferidos = exatos.filter(c => normalizar(c.path) === "database");
       const opcoes = preferidos.length ? preferidos : exatos;
       const alvo = opcoes.length === 1 ? opcoes[0] : null;
      if (!alvo) continue;
      const valorServico = {id: alvo.id, name: alvo.name, path: alvo.path || "", allowSelection: true,
        allowFinishTicket: alvo.allowFinishTicket !== false, serviceForTicketType: alvo.serviceForTicketType ?? 0,
        description: alvo.description ?? null, automationMacroId: alvo.automationMacroId ?? null};
       dadosWidget.setValue(valorServico);
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
             {
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
               {
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

  async function preencherClassificacao() {
   try {
    const categoria = normalizar(dados.categoria || "Alerta").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const padroesCat = [new RegExp(`^${categoria}$`)];
    const padroesUrg = padroesUrgencia(dados.severidade);
    const categorias = localizarCampos('select[name*="Category" i], input[name*="Category" i], select[id*="Category" i], input[id*="Category" i], select[name*="Categoria" i], input[name*="Categoria" i], select[id*="Categoria" i], input[id*="Categoria" i], input.category', ["categoria", "category"]);
    const urgencias = localizarCampos('select[name*="Urgency" i], input[name*="Urgency" i], select[id*="Urgency" i], input[id*="Urgency" i], select[name*="Urgencia" i], input[name*="Urgencia" i], select[id*="Urgencia" i], input[id*="Urgencia" i], select[name*="Severity" i], select[id*="Severity" i], input.urgency', ["urgencia", "urgency", "severidade"]);
    if (categorias.length) campos.categoria = "pendente";
    if (urgencias.length) campos.urgencia = "pendente";
    if (await selecionarCampo(categorias, padroesCat)) campos.categoria = "preenchido";
    if (await selecionarCampo(urgencias, padroesUrg)) campos.urgencia = "preenchido";
  } catch {}
  }
  await preencherClassificacao();

  const emSecaoVisivel = el => {
    const secao = el.closest("section");
    return !secao || secao.getClientRects().length > 0;
  };
  async function preencherRelacionamentos() {
   try {
    if (dados.solicitante) {
      const alvos = localizarCampos('input.clients, input.requester, input.client, input[name*="Client" i], select[name*="Requester" i]', ["solicitante", "cliente"]).filter(emSecaoVisivel);
      campos.solicitante = alvos.length ? "pendente" : "nao_localizado";
      if (await selecionarSolicitante(alvos, String(dados.solicitante).split(/[,;]/)[0].trim())) campos.solicitante = "preenchido";
    }
    const servicoAlvo = resolverServico(dados);
    if (servicoAlvo) {
      const alvos = localizarCampos(seletores.servico, ["servico"]).filter(emSecaoVisivel);
      campos.servico = alvos.length ? "pendente" : "nao_localizado";
      if (await selecionarServico(alvos, servicoAlvo)) campos.servico = "preenchido";
    }
  } catch {}
  }
  await preencherRelacionamentos();

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
  async function preencherHoras() {
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
  }
  await preencherHoras();

  // 4. Editor de Texto Rico (Froala / TinyMCE / Kendo / iframe)
  async function preencherDescricao() {
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
  const vazio = el => !el.textContent.replace(/[\s\u200b\u00a0]/g, "") &&
    !el.querySelector?.('img, video, iframe, table, hr') && !el.matches?.('img, video, iframe, table, hr');
  function limparBorda(el, inicio) {
    let filho = inicio ? el.firstChild : el.lastChild;
    while (filho && vazio(filho)) {
      filho.remove();
      filho = inicio ? el.firstChild : el.lastChild;
    }
    if (filho?.nodeType === Node.ELEMENT_NODE && /^(DIV|P|SPAN)$/.test(filho.tagName)) {
      limparBorda(filho, inicio);
      if (inicio) filho.style.marginTop = "0";
      else filho.style.marginBottom = "0";
    }
  }
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
    limparBorda(evidencia, false);
    limparBorda(conteudoAtual, true);
    htmlFinal = `${evidencia.innerHTML}${conteudoAtual.innerHTML}`;
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
        for (const img of novas) {
          const anterior = img.parentElement;
          img.style.display = "block";
          img.style.margin = "0";
          caixa.append(img);
          if (anterior && anterior !== corpo && vazio(anterior)) anterior.remove();
        }
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
    return preenchido && texto(recebido).includes(texto(esperado)) &&
       Array.from(esperado.querySelectorAll("img")).every(img => arquivos.length ? imagens.some(src => src && !/^(data:|blob:)/.test(src)) : imagens.includes(img.getAttribute("src")));
  }

   if (!await preencherDescricao() || assunto.value !== dados.assunto) {
    throw new Error("O formulário não confirmou o preenchimento. Revise a guia aberta.");
  }
   campos.assunto = "preenchido";
   campos.descricao = "preenchido";
    if (tipoInicial.radio || tipoInicial.rotulo) campos.tipo = tipoConfirmado() ? "preenchido" : "pendente";
   try {
     const servicoFinal = resolverServico(dados);
     if (servicoFinal) {
       // A última checagem apenas observa: não desfaz uma edição feita durante o upload.
       const alvosServico = localizarCampos(seletores.servico, ["servico"]).filter(emSecaoVisivel);
       const confirmado = alvosServico.some(el => normalizar((jq ? jq(el).data()?.getValue?.() : null)?.name) === normalizar(servicoFinal));
       campos.servico = confirmado ? "preenchido" : "pendente";
     }
   } catch {}
   if (dados.exigir_interno && campos.tipo !== "preenchido") {
     throw new Error("Não foi possível confirmar o tipo Interno. Selecione INTERNO antes de salvar o ticket.");
   }
   return {ok: true, campos};
} catch (err) {
  return {erro: err.message || String(err)};
}
}
