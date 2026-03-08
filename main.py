import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
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

# --- FUNÇÕES UTILITÁRIAS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    variantes = {termo}
    if termo.endswith("s"): variantes.add(termo[:-1])
    else: variantes.add(termo + "s")
    return list(variantes)

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# Lógica de cálculo avançada (do main.py)
def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    q_rolos = int(match_leve.group(1)) if match_leve else (int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)) else None)
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg".replace('.', ',')
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)) else None
    folhas_por_unidade = int(m.group(1)) if (m := re.search(r'(\d+)\s*(folhas|toalhas)(?:\s*cada)?', desc)) else None
    if qtd_unidades and folhas_por_unidade: return qtd_unidades * folhas_por_unidade, preco_total / (qtd_unidades * folhas_por_unidade)
    if folhas_por_unidade: return folhas_por_unidade, preco_total / folhas_por_unidade
    return None, None

def calc_unitario_nagumo(preco, desc, nome):
    fonte = f"{nome} {desc}".lower()
    m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo|g|gramas?)", fonte)
    if m_kg:
        val = float(m_kg.group(1).replace(',', '.'))
        if 'g' in m_kg.group(2) and 'kg' not in m_kg.group(2): val /= 1000
        return f"R$ {preco/val:.2f}/kg" if val > 0 else f"R$ {preco:.2f}/un", (preco/val if val > 0 else preco)
    return f"R$ {preco:.2f}/un", preco

# --- API ---
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        return r.json().get('data', {}).get('produtos', []) if r.status_code == 200 else []
    except: return []

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    payload = {"query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }",
               "variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50, "search": [{"query": term}]}}}
    try:
        r = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

# --- INTERFACE ---
st.set_page_config(page_title="Preços Mercados", layout="wide")
st.markdown("<style>.block-container{padding-top:1rem;} footer{visibility:hidden;} .product-container{display:flex;align-items:center;gap:10px;}</style>", unsafe_allow_html=True)
termo = st.text_input("🔎 Pesquisar produto:", "Banana")

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    
    with st.spinner("Buscando..."):
        # Shibata
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        shibata_final = []
        vistos = set()
        for p in raw_shibata:
            if p['id'] not in vistos:
                vistos.add(p['id'])
                oferta = p.get('oferta')
                p['preco_final'] = float(oferta.get('preco_oferta') if (p.get('em_oferta') and oferta) else p.get('preco', 0))
                shibata_final.append(p)

        # Nagumo
        nagumo_final = []
        vistos_n = set()
        for t in termos_busca:
            for p in buscar_nagumo(t):
                if p['sku'] not in vistos_n:
                    vistos_n.add(p['sku'])
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    p['preco_final'] = cond[0].get('price') if (promo.get('isActive') and cond) else p.get('price', 0)
                    p['preco_original'] = p.get('price', 0)
                    nagumo_final.append(p)

    with col1:
        st.image(LOGO_SHIBATA_URL, width=80)
        for p in shibata_final:
            preco_formatado = f"R$ {p['preco_final']:.2f}".replace('.', ',')
            st.markdown(f"**{p['descricao']}**<br>{preco_formatado}", unsafe_allow_html=True)
            st.divider()

    with col2:
        st.image(LOGO_NAGUMO_URL, width=80)
        for p in nagumo_final:
            preco_final = p['preco_final']
            preco_orig = p['preco_original']
            promo_html = f"<br><span style='color:red;'>{((preco_orig-preco_final)/preco_orig)*100:.0f}% OFF</span>" if preco_final < preco_orig else ""
            st.markdown(f"**{p['name']}**<br>R$ {preco_final:.2f}{promo_html}", unsafe_allow_html=True)
            st.divider()
