"""Resumo de consumo informado pelas APIs, mantido apenas na sessão atual."""


class ConsumoIA:
    def __init__(self):
        self.ultimos = {}
        self.totais = {}

    def registrar(self, dados):
        provedor = dados["provedor"]
        self.ultimos[provedor] = dados
        if dados.get("total") is not None:
            self.totais[provedor] = self.totais.get(provedor, 0) + dados["total"]

    def resumo(self, config):
        linhas = [f"Teto de resposta: Gemini {config.gemini_max_output_tokens} · Groq {config.groq_max_completion_tokens} tokens"]
        for provedor in ("Gemini", "Groq"):
            dados = self.ultimos.get(provedor)
            if dados is None:
                linhas.append(f"{provedor}: aguardando consulta nesta sessão.")
                continue
            def valor(campo):
                v = dados.get(campo)
                return "não informado" if v is None else str(v)
            linhas.append(f"{provedor} · {dados['horario']} · Entrada: {valor('entrada')} · Saída: {valor('saida')} · Total: {valor('total')}")
            linhas.append(f"Total reportado nesta sessão: {self.totais.get(provedor, 0)} tokens.")
            if provedor == "Groq":
                cotas = dados.get("cotas", {})
                for unidade, sufixo in (("Tokens/min", "tokens"), ("Requisições/dia", "requests")):
                    restante = cotas.get(f"x-ratelimit-remaining-{sufixo}", "não informado")
                    limite = cotas.get(f"x-ratelimit-limit-{sufixo}", "não informado")
                    reset = cotas.get(f"x-ratelimit-reset-{sufixo}", "não informado")
                    linhas.append(f"{unidade}: restantes {restante} / limite {limite} · Renovação informada: {reset}")
                if "retry-after" in cotas:
                    linhas.append(f"Nova tentativa após {cotas['retry-after']} segundos (informado pela Groq).")
        linhas.append("Gemini: cota restante não disponível nesta integração; consulte o AI Studio.")
        linhas.append("Cotas refletem a última resposta, sem atualização em tempo real. Totais da sessão incluem apenas consumo reportado.")
        return "\n".join(linhas)
