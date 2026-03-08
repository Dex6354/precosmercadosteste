import streamlit as st
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações para Shibata
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

# Links dos logos
LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES UTILITÁRIAS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

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

def formatar_preco_unidade_personalizado(preco_total, quantidade, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    unidade = unidade.lower()
    if quantidade and quantidade != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(quantidade).replace('.', ',')}{unidade}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{unidade}"

# --- LÓGICA DE CÁLCULO ---
def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    patterns = [
        (r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', 1),
        (r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', 1000),
        (r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', 1),
        (r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', 1000)
    ]
    for p, div in patterns:
        m = re.search(p, desc_minus)
        if m:
            val = float(m.group(1).replace(',', '.')) / div
            return preco_total / val if val > 0 else None, f"R$ {preco_total/val:.2f}/un"
    return None, None

def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

# --- BUSCA SHIBATA ---
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        response = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {}).get('produtos', [])
            return [p for p in data if p.get("disponivel", True)]
    except: pass
    return []

# --- BUSCA NAGUMO (CORRIGIDA) ---
def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.nagumo.com",
        "User-Agent": "Mozilla/5.0",
        "apollographql-client-name": "Ecommerce SSR"
    }
    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "searchProductsInput": {
                "clientId": "NAGUMO", "storeReference": "22", "currentPage": 1,
                "pageSize": 50, "search": [{"query": term}]
            }
        },
        "query": """query SearchProducts($searchProductsInput: SearchProductsInput!) {
            searchProducts(searchProductsInput: $searchProductsInput) {
                products { name price photosUrl sku description unit 
                    promotion { isActive conditions { price } }
                }
            }
        }"""
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_json = response.json()
        # Verificação robusta para evitar NoneType attribute access
        data = res_json.get("data")
        if data:
            search_products = data.get("searchProducts")
            if search_products:
                return search_products.get("products") or []
    except Exception as e:
        st.error(f"Erro no Nagumo: {e}")
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")
st.markdown("<style>header{display:none;} [data-testid='stColumn']{overflow-y:auto; max-height:85vh; border:1px solid #ddd; padding:10px; border-radius:8px;}</style>", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    termos_expandidos = gerar_formas_variantes(remover_acentos(termo))
    col1, col2 = st.columns(2)

    with st.spinner("Buscando..."):
        # SHIBATA
        prod_shibata = []
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = [ex.submit(buscar_pagina_shibata, t, 1) for t in termos_expandidos]
            for f in as_completed(futures): prod_shibata.extend(f.result())
        
        # NAGUMO
        prod_nagumo = []
        for t in termos_expandidos:
            res = buscar_nagumo(t)
            if res: prod_nagumo.extend(res)

    # Exibição Shibata
    with col1:
        st.image(LOGO_SHIBATA_URL, width=100)
        for p in prod_shibata[:20]:
            p_id = p.get('produto_id')
            p_slug = slugify(p.get('descricao', ''))
            link = f"https://www.loja.shibata.com.br/produto/{p_id}/{p_slug}"
            preco = p.get('preco_oferta') or p.get('preco', 0)
            
            st.markdown(f"""
            <div style='display:flex; gap:10px; margin-bottom:10px;'>
                <img src="https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/100x100/{p.get('imagem')}" width="50">
                <div>
                    <a href='{link}' style='font-size:12px;'>{p.get('descricao')}</a><br>
                    <strong>R$ {preco:.2f}</strong>
                </div>
            </div>
            <hr>
            """, unsafe_allow_html=True)

    # Exibição Nagumo
    with col2:
        st.image(LOGO_NAGUMO_URL, width=100)
        seen_sku = set()
        for p in prod_nagumo:
            if p['sku'] in seen_sku: continue
            seen_sku.add(p['sku'])
            
            promocao = p.get('promotion') or {}
            preco = p['price']
            if promocao.get('isActive') and promocao.get('conditions'):
                preco = promocao['conditions'][0]['price']
            
            img = p['photosUrl'][0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
            link = f"https://www.nagumo.com/p/{p['sku']}"
            
            st.markdown(f"""
            <div style='display:flex; gap:10px; margin-bottom:10px;'>
                <img src="{img}" width="50">
                <div>
                    <a href='{link}' style='font-size:12px;'>{p['name']}</a><br>
                    <strong>R$ {preco:.2f}</strong>
                </div>
            </div>
            <hr>
            """, unsafe_allow_html=True)
