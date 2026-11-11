"""Gera os userscripts a partir dos mesmos coletores usados na extensão."""

from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def artefatos():
    for nome, descricao, matches, arquivos in (
        ("Zabbix", "Coleta local de eventos, seleção em lote e imagens sob demanda", ["https://zabbix.example.com/*", "https://zabbix-secondary.example.com/*"], ["coletor.js", "zabbix.js"]),
        ("Movidesk", "Copia número, assunto, link e template sem polling periódico", ["https://*.movidesk.com/*"], ["movidesk.js"]),
    ):
        cabecalho = "\n".join([
            "// ==UserScript==", f"// @name         NOCFlow - {nome} - Local", "// @namespace    nocflow",
            "// @version      2.1.0", f"// @description  {descricao}",
            *(f"// @match        {match}" for match in matches),
            "// @grant        none", "// @run-at       document-idle", "// ==/UserScript==", "",
            "// Gerado por gerar_userscripts.py; edite as fontes em edge_extension/.", "",
        ])
        yield f"NOCFlow-{nome}.user.js", cabecalho + "\n".join((RAIZ / "edge_extension" / a).read_text(encoding="utf-8") for a in arquivos)


if __name__ == "__main__":
    destino = RAIZ / "tampermonkey"
    destino.mkdir(exist_ok=True)
    for nome, conteudo in artefatos():
        (destino / nome).write_text(conteudo, encoding="utf-8", newline="\n")
        print(nome)
