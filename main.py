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

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    return None, None

def formatar_preco_shibata(preco_total, qtd, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

# --- LÓGICA BUSCA ---
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if r.status_code == 200: return r.json().get('data', {}).get('produtos', [])
    except: pass
    return []

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {"Content-Type": "application/json", "Origin": "https://www.nagumo.com", "User-Agent": "Mozilla/5.0"}
    payload = {
        "operationName": "SearchProducts",
        "variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50, "search": [{"query": term}], "filters": {}}},
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

def calc_unitario_nagumo(preco, desc, nome, unit_api):
    fonte = f"{nome} {desc}".lower()
    m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo|g|gramas?)", fonte)
    if m_kg:
        val = float(m_kg.group(1).replace(',', '.'))
        if 'g' in m_kg.group(2) and 'kg' not in m_kg.group(2): val /= 1000
        if val > 0: return f"R$ {preco/val:.2f}/kg", preco/val
    return f"R$ {preco:.2f}/{unit_api or 'un'}", preco

# --- INTERFACE ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        header[data-testid="stHeader"] { display: none; }
        
        /* Container da Coluna */
        [data-testid="stColumn"] {
            overflow-y: auto;
            max-height: 85vh;
            padding: 10px;
            border: 1px solid #f0f2f6;
            border-radius: 8px;
            background: transparent;
            position: relative;
            scrollbar-width: thin;
        }

        /* Botão Flutuante (FAB) */
        .fab-container {
            position: -webkit-sticky;
            position: sticky;
            top: 75vh; /* Fixa na parte de baixo da área visível */
            z-index: 9999;
            height: 0;
            display: flex;
            justify-content: flex-end;
            pointer-events: none;
        }

        .fab-button {
            pointer-events: auto;
            background-color: #333;
            color: white !important;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            text-decoration: none;
            font-size: 20px;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
            border: 2px solid white;
        }

        .product-container { display: flex; align-items: center; gap: 10px; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        div, span, strong, small { font-size: 0.75rem !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("Buscando..."):
        # Processamento Shibata
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 4)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        shibata_final = []
        vistos_s = set()
        for p in raw_shibata:
            if p.get('id') not in vistos_s:
                vistos_s.add(p.get('id'))
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta')
                    preco_f = float(oferta.get('preco_oferta')) if (p.get('em_oferta') and oferta) else float(p.get('preco') or 0)
                    p['url'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    p['p_str'] = formatar_preco_shibata(preco_f, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['sort'], u_inf = calcular_preco_unidade(desc, preco_f)
                    p['unit'] = u_inf or ""
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x['sort'] or 999)

        # Processamento Nagumo
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        nagumo_final = []
        vistos_n = set()
        for p in raw_nagumo:
            if p.get('sku') not in vistos_n:
                vistos_n.add(p.get('sku'))
                if all(k in remover_acentos(f"{p['name']} {p['description']}") for k in palavras_chave):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    preco_f = cond[0].get('price') if (promo.get('isActive') and cond) else p.get('price', 0)
                    p['url'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(p['name'])}-{p['sku']}.html"
                    label, s_v = calc_unitario_nagumo(preco_f, p['description'], p['name'], p.get('unit'))
                    p['unit'], p['sort'], p['p_final'] = label, s_v, preco_f
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort'] or 999)

    # Coluna 1
    with col1:
        st.markdown("<div id='top_s'></div>", unsafe_allow_html=True)
        st.markdown(f"<center><img src='{LOGO_SHIBATA_URL}' width='80' style='background:white; padding:3px; border-radius:4px;'/></center>", unsafe_allow_html=True)
        if shibata_final:
            st.markdown("<div class='fab-container'><a href='#top_s' class='fab-button'>↑</a></div>", unsafe_allow_html=True)
            for p in shibata_final:
                img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
                st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url']}' target='_blank'><img src='{img}' width='70'/></a>
                    <div class='product-info'><b>{p['descricao']}</b><br><b>{p['p_str']}</b><br><span style='color:gray;'>{p['unit']}</span></div>
                </div><hr class='product-separator'/>
                """, unsafe_allow_html=True)

    # Coluna 2
    with col2:
        st.markdown("<div id='top_n'></div>", unsafe_allow_html=True)
        st.markdown(f"<center><img src='{LOGO_NAGUMO_URL}' width='80' style='border:1px solid white; border-radius:4px;'/></center>", unsafe_allow_html=True)
        if nagumo_final:
            st.markdown("<div class='fab-container'><a href='#top_n' class='fab-button'>↑</a></div>", unsafe_allow_html=True)
            for p in nagumo_final:
                imgs = p.get('photosUrl')
                img = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
                st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url']}' target='_blank'><img src='{img}' width='70'/></a>
                    <div style='flex:1;'><b>{p['name']}</b><br><b>R$ {p['p_final']:.2f}</b><br><span style='color:gray;'>{p['unit']}</span></div>
                </div><hr class='product-separator'/>
                """, unsafe_allow_html=True)

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(c => c.scrollTop = 0);</script>", height=0)
