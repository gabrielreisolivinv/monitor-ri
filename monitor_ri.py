#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Monitor de Fatos Relevantes e Resultados (CVM/RAD) -> alerta no WhatsApp.

Consulta o sistema RAD da CVM (onde as companhias protocolam os documentos),
filtra as empresas e categorias configuradas abaixo e manda uma mensagem no
WhatsApp (via CallMeBot) para cada documento novo.

Uso:
    python monitor_ri.py            # execução normal (é o que o GitHub roda)
    python monitor_ri.py --teste    # manda uma mensagem de teste no WhatsApp
    python monitor_ri.py --listar   # mostra o que a CVM tem desta semana p/ suas empresas
"""

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urlencode

import requests

# ============================================================================
# CONFIGURAÇÃO — edite aqui
# ============================================================================

# Cada ticker é reconhecido pelo nome da companhia como aparece na CVM.
# Os padrões são comparados sem acento e em maiúsculas.
EMPRESAS = {
    "VALE3": [r"\bVALE S\.?A\b"],
    "PETR4": [r"PETROLEO BRASILEIRO"],
    "ITUB4": [r"ITAU UNIBANCO HOLDING"],
    "RANI3": [r"IRANI PAPEL"],
    "BBAS3": [r"\bBCO BRASIL\b", r"\bBANCO DO BRASIL\b"],
    "CXSE3": [r"CAIXA SEGURIDADE"],
    "BBSE3": [r"\bBB SEGURIDADE"],
    "TIMS3": [r"^TIM S\.?A\b"],
    "CMIG4": [r"ENERGETICA DE MINAS GERAIS"],
    "ISAE4": [r"ISA ENERGIA BRASIL", r"TRANSMISSAO DE ENERGIA ELETRICA PAULISTA"],
    "CPFL3": [r"^CPFL ENERGIA S\.?A\b"],
}

# Categorias que geram alerta (comparação pelo começo do nome, sem acento).
CATEGORIAS = [
    "FATO RELEVANTE",
    "ITR",                          # resultado trimestral
    "DFP",                          # resultado anual
    "DADOS ECONOMICO-FINANCEIROS",  # release de resultados, apresentações
    # "COMUNICADO AO MERCADO",      # tire o # para receber também comunicados
    # "AVISO AOS ACIONISTAS",       # e avisos (dividendos/JCP)
]

# ============================================================================

RAD = "https://www.rad.cvm.gov.br/ENET/"
URL_CONSULTA = RAD + "frmConsultaExternaCVM.aspx"
URL_LISTA = URL_CONSULTA + "/ListarDocumentos"
URL_VISUALIZAR = RAD + "frmExibirArquivoIPEExterno.aspx"
URL_DOWNLOAD = RAD + "frmDownloadDocumento.aspx"

ARQ_ESTADO = Path(__file__).parent / "vistos.json"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

EMOJI = {"FATO RELEVANTE": "🚨", "ITR": "📊", "DFP": "📊",
         "DADOS ECONOMICO-FINANCEIROS": "📈"}


def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", txt).strip().upper()


def limpar_html(txt: str) -> str:
    return re.sub(r"<[^>]+>", " ", txt or "").replace("&nbsp;", " ").strip()


def ticker_da_empresa(nome: str):
    n = normalizar(nome)
    for ticker, padroes in EMPRESAS.items():
        if any(re.search(p, n) for p in padroes):
            return ticker
    return None


def categoria_monitorada(cat: str):
    c = normalizar(cat)
    for alvo in CATEGORIAS:
        if c.startswith(alvo):
            return alvo
    return None


# ---------------------------------------------------------------------------
# CVM
# ---------------------------------------------------------------------------

def buscar_documentos_cvm() -> str:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Referer": URL_CONSULTA,
                      "Accept-Language": "pt-BR,pt;q=0.9"})
    try:
        s.get(URL_CONSULTA, timeout=30)
    except requests.RequestException:
        pass

    payload = {
        "dataDe": "", "dataAte": "", "empresa": "", "setorAtividade": "-1",
        "categoriaEmissor": "-1", "situacaoEmissor": "A", "tipoParticipante": "1",
        "dataReferencia": "", "categoria": "", "periodo": "1",  # 1 = esta semana
        "horaIni": "", "horaFim": "", "palavraChave": "", "ultimaDtRef": "false",
        "tipoEmpresa": "2", "token": "", "versaoCaptcha": "V3",
    }
    r = s.post(URL_LISTA, json=payload, timeout=60,
               headers={"Content-Type": "application/json; charset=utf-8",
                        "X-Requested-With": "XMLHttpRequest"})
    r.raise_for_status()
    d = r.json().get("d", {})
    if isinstance(d, dict):
        if d.get("temErro"):
            raise RuntimeError("CVM retornou erro: " + str(d.get("msgErro")))
        return d.get("dados", "") or ""
    return d if isinstance(d, str) else ""


def interpretar(bruto: str, somente_monitorados=True):
    """Linhas separadas por '&*', colunas por '$&'."""
    docs, linhas_validas = [], 0
    for linha in bruto.split("&*"):
        col = linha.split("$&")
        if len(col) < 11:
            continue
        linhas_validas += 1
        empresa = limpar_html(col[1])
        categoria = limpar_html(col[2])
        ticker = ticker_da_empresa(empresa)
        cat = categoria_monitorada(categoria)
        if somente_monitorados and not (ticker and cat):
            continue
        m = re.search(r"OpenDownloadDocumentos\(\s*'(\d+)'\s*,\s*'(\d+)'\s*,"
                      r"\s*'(\d+)'\s*,\s*'([^']+)'", col[10])
        if not m:
            continue
        seq, versao, protocolo, tipo_desc = m.groups()
        data = re.sub(r"^\d{8}\s*", "", limpar_html(col[6])).strip()
        docs.append({
            "ticker": ticker, "empresa": empresa, "categoria": categoria,
            "cat_chave": cat, "tipo": limpar_html(col[3]),
            "assunto": limpar_html(col[11]) if len(col) > 11 else "",
            "data": data, "protocolo": protocolo,
            "link": (URL_VISUALIZAR + "?" + urlencode({"NumeroProtocoloEntrega": protocolo})
                     if tipo_desc.upper() == "IPE" else
                     URL_DOWNLOAD + "?" + urlencode({
                         "Tela": "ext", "numSequencia": seq, "numVersao": versao,
                         "numProtocolo": protocolo, "descTipo": tipo_desc,
                         "CodigoInstituicao": "1"})),
        })
    return docs, linhas_validas


# ---------------------------------------------------------------------------
# WhatsApp (CallMeBot)
# ---------------------------------------------------------------------------

def enviar_whatsapp(texto: str) -> bool:
    fone = os.environ.get("WHATSAPP_NUMERO", "").strip()
    chave = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    if not fone or not chave:
        print("ERRO: defina WHATSAPP_NUMERO e CALLMEBOT_APIKEY.")
        return False
    url = ("https://api.callmebot.com/whatsapp.php?phone=" + quote(fone)
           + "&text=" + quote(texto) + "&apikey=" + quote(chave))
    for tentativa in range(3):
        try:
            r = requests.get(url, timeout=30)
            resposta = re.sub(r"<[^>]+>", " ", r.text)
            resposta = re.sub(r"\s+", " ", resposta).strip()
            if r.ok and not any(p in resposta.lower() for p in ("error", "invalid")):
                return True
            print(f"CallMeBot recusou ({r.status_code}): {resposta[:200]}")
            if "invalid" in resposta.lower():
                return False  # chave/numero errados: nao adianta repetir
        except requests.RequestException as e:
            print(f"Falha ao enviar WhatsApp: {e}")
        time.sleep(5 * (tentativa + 1))
    return False


def montar_mensagem(doc) -> str:
    emoji = EMOJI.get(doc["cat_chave"], "📄")
    partes = [f"{emoji} *{doc['ticker']}* – {doc['categoria']}"]
    detalhe = " | ".join(x for x in (doc["tipo"], doc["assunto"]) if x)
    if detalhe:
        partes.append(detalhe[:300])
    partes.append(f"🕒 {doc['data']}")
    partes.append(doc["link"])
    return "\n".join(partes)


# ---------------------------------------------------------------------------

def carregar_vistos():
    if ARQ_ESTADO.exists():
        return set(json.loads(ARQ_ESTADO.read_text(encoding="utf-8")))
    return None


def salvar_vistos(vistos):
    # guarda só os últimos 3000 protocolos para o arquivo não crescer sem fim
    lista = sorted(vistos, key=lambda p: int(p) if p.isdigit() else 0)[-3000:]
    ARQ_ESTADO.write_text(json.dumps(lista, indent=0), encoding="utf-8")


def main() -> int:
    if "--teste" in sys.argv:
        ok = enviar_whatsapp("✅ Teste do monitor de RI: se você recebeu isto, "
                             "o WhatsApp está configurado.")
        print("Enviado!" if ok else "Não foi possível enviar.")
        return 0 if ok else 1

    bruto = buscar_documentos_cvm()
    docs, validas = interpretar(bruto)

    # Canário: a consulta cobre todas as empresas da semana, então SEMPRE vem
    # muita coisa. Zero linhas = a CVM mudou algo; falhar faz o GitHub te avisar.
    if validas == 0:
        print("ERRO: a CVM respondeu sem nenhum documento. O formato pode ter mudado.")
        return 1

    if "--listar" in sys.argv:
        print(f"{validas} documentos na semana (todas as empresas). Das suas:")
        for d in docs:
            print(f"  {d['ticker']:6} {d['data']:17} {d['categoria']} | {d['assunto']}")
        return 0

    vistos = carregar_vistos()
    if vistos is None:
        # Primeira execução: marca o que já existe como visto, sem disparar alertas.
        salvar_vistos({d["protocolo"] for d in docs})
        enviar_whatsapp("✅ Monitor de RI ativado. Acompanhando: "
                        + ", ".join(EMPRESAS) + ".")
        print(f"Primeira execução: {len(docs)} documentos marcados como vistos.")
        return 0

    novos = [d for d in docs if d["protocolo"] not in vistos]
    print(f"{validas} documentos na semana | {len(docs)} das suas empresas | {len(novos)} novos")
    for d in novos:
        if enviar_whatsapp(montar_mensagem(d)):
            vistos.add(d["protocolo"])   # só marca como visto se o aviso chegou
            print("Avisado:", d["ticker"], d["categoria"], d["assunto"])
        time.sleep(3)
    salvar_vistos(vistos)
    return 0


if __name__ == "__main__":
    sys.exit(main())



