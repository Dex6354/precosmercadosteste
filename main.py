import streamlit as st
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9..."
ORG_ID = "161"

HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"


def remover_acentos(texto):
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower()


def gerar_formas_variantes(termo):
    variantes = {termo}
    if termo.endswith("s"):
        variantes.add(termo[:-1])
    else:
        variantes.add(termo + "s")
    return list(variantes)


def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text


# -----------------------
# CALCULOS UNIFICADOS
# -----------------------

def calcular_preco_unidade(descricao, preco_total):

    desc = remover_acentos(descricao)

    match_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc)
    if match_kg:
        peso = float(match_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"

    match_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc)
    if match_g:
        peso = float(match_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"

    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"

    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"

    return None, None


def calcular_precos_papel(descricao, preco_total):

    desc = descricao.lower()

    match_leve = re.search(r'leve\s*(\d+)', desc)

    if match_leve:
        q_rolos = int(match_leve.group(1))
    else:
        match_rolos = re.search(r'(\d+)\s*(rolos|unidades)', desc)
        q_rolos = int(match_rolos.group(1)) if match_rolos else None

    match_metros = re.search(r'(\d+)\s*m', desc)

    m_rolos = float(match_metros.group(1)) if match_metros else None

    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}/m"

    return None, None


def calcular_preco_papel_toalha(descricao, preco_total):

    desc = descricao.lower()

    qtd = None
    folhas = None

    m = re.search(r'(\d+)\s*(rolos|unidades)', desc)
    if m:
        qtd = int(m.group(1))

    f = re.search(r'(\d+)\s*folhas', desc)
    if f:
        folhas = int(f.group(1))

    if qtd and folhas:
        total = qtd * folhas
        return total, preco_total / total

    if folhas:
        return folhas, preco_total / folhas

    return None, None


# -----------------------
# BUSCA SHIBATA
# -----------------------

def buscar_pagina_shibata(termo, pagina):

    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"

    r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)

    if r.status_code == 200:
        return r.json().get("data", {}).get("produtos", [])

    return []


# -----------------------
# BUSCA NAGUMO
# -----------------------

def buscar_nagumo(term):

    url = "https://nextgentheadless.instaleap.io/api/v3"

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.nagumo.com"
    }

    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "searchProductsInput": {
                "clientId": "NAGUMO",
                "storeReference": "22",
                "currentPage": 1,
                "pageSize": 50,
                "search": [{"query": term}],
                "filters": {}
            }
        },
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }"
    }

    r = requests.post(url, headers=headers, json=payload, timeout=10)

    return r.json().get('data', {}).get('searchProducts', {}).get('products', [])


# -----------------------
# STREAMLIT
# -----------------------

st.set_page_config(
    page_title="Preços Mercados",
    page_icon="🛒",
    layout="wide"
)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)

termo = st.text_input("🔎 Digite o nome do produto:", "banana").lower()

termos_expandidos = gerar_formas_variantes(remover_acentos(termo))

if termo:

    col1, col2 = st.columns(2)

    # -----------------------
    # SHIBATA
    # -----------------------

    produtos_shibata = []

    with ThreadPoolExecutor(max_workers=8) as executor:

        futures = [
            executor.submit(buscar_pagina_shibata, t, p)
            for t in termos_expandidos
            for p in range(1, 10)
        ]

        for future in as_completed(futures):
            produtos_shibata.extend(future.result())

    # -----------------------
    # NAGUMO
    # -----------------------

    produtos_nagumo = []

    for t in termos_expandidos:
        produtos_nagumo.extend(buscar_nagumo(t))

    # -----------------------
    # EXIBIÇÃO SHIBATA
    # -----------------------

    with col1:

        st.image(LOGO_SHIBATA_URL, width=80)

        for p in produtos_shibata:

            nome = p.get("descricao", "")
            preco = float(p.get("preco") or 0)

            descricao_mod = nome

            descricao_mod = re.sub(
                r'(folha simples)',
                r"<span style='color:red'><b>\1</b></span>",
                descricao_mod,
                flags=re.IGNORECASE
            )

            descricao_mod = re.sub(
                r'(folha dupla|folha tripla)',
                r"<span style='color:green'><b>\1</b></span>",
                descricao_mod,
                flags=re.IGNORECASE
            )

            st.markdown(f"**{descricao_mod}**", unsafe_allow_html=True)

            st.write(f"R$ {preco:.2f}")

    # -----------------------
    # EXIBIÇÃO NAGUMO
    # -----------------------

    with col2:

        st.image(LOGO_NAGUMO_URL, width=80)

        for p in produtos_nagumo:

            nome = p.get("name", "")
            desc = p.get("description", "")
            preco = float(p.get("price") or 0)

            descricao = f"{nome} {desc}"

            preco_un, preco_un_str = calcular_preco_unidade(descricao, preco)
            metro_val, metro_str = calcular_precos_papel(descricao, preco)
            folhas, preco_folha = calcular_preco_papel_toalha(descricao, preco)

            descricao_mod = nome

            descricao_mod = re.sub(
                r'(folha simples)',
                r"<span style='color:red'><b>\1</b></span>",
                descricao_mod,
                flags=re.IGNORECASE
            )

            descricao_mod = re.sub(
                r'(folha dupla|folha tripla)',
                r"<span style='color:green'><b>\1</b></span>",
                descricao_mod,
                flags=re.IGNORECASE
            )

            st.markdown(f"**{descricao_mod}**", unsafe_allow_html=True)

            st.write(f"R$ {preco:.2f}")

            if preco_folha:
                st.caption(f"R$ {preco_folha:.3f}/folha")

            elif metro_str:
                st.caption(metro_str)

            elif preco_un_str:
                st.caption(preco_un_str)
