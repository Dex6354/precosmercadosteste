import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES ---
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "organizationid": ORG_ID, "User-Agent": "Mozilla/5.0"}
LOGO_SHIBATA = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
LOGO_NAGUMO = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"

# --- FUNÇÕES ---
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    variantes = {termo}
    variantes.add(termo[:-1] if termo.endswith("s") else termo + "s")
    return list(variantes)

def slugify(text):
    text = re.sub(r'[^a-z0-9\s-]', '', remover_acentos(text)).strip()
    return re.sub(r'[-\s]+', '-', text)

# --- BUSCAS ---
def buscar_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        return r.json().get('data', {}).get('produtos', []) if r.status_code == 200 else []
    except: return []

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    payload = {"variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "search": [{"query": term}]}}, 
               "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price sku description unit promotion { isActive conditions { price } } } } }"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

# --- INTERFACE ---
st.set_page_config(layout="wide")
st.markdown("<style>[data-testid='stColumn']{border:1px solid #eee; padding:10px; border-radius:8px;}</style>", unsafe_allow_html=True)
termo = st.text_input("🔎 Produto:", "Banana")

if termo:
    col1, col2 = st.columns(2)
    termos = gerar_formas_variantes(remover_acentos(termo))
    
    with st.spinner("Buscando..."):
        # Shibata (Com range 1 a 6 para garantir todos os itens)
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_shibata, t, p) for t in termos for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        shibata_final = {p['id']: p for p in raw_shibata}.values()

        # Nagumo
        nagumo_final = []
        vistos = set()
        for t in termos:
            for p in buscar_nagumo(t):
                if p['sku'] not in vistos:
                    vistos.add(p['sku'])
                    nagumo_final.append(p)

    with col1:
        st.image(LOGO_SHIBATA, width=80)
        for p in shibata_final:
            oferta = p.get('oferta') or {}
            preco = float(oferta.get('preco_oferta') if p.get('em_oferta') else p.get('preco', 0))
            st.markdown(f"**{p['descricao']}**<br>R$ {preco:.2f}", unsafe_allow_html=True)
            st.divider()

    with col2:
        st.image(LOGO_NAGUMO, width=80)
        for p in nagumo_final:
            promo = p.get('promotion') or {}
            preco = promo.get('conditions', [{}])[0].get('price') if promo.get('isActive') else p.get('price', 0)
            st.markdown(f"**{p['name']}**<br>R$ {preco:.2f}", unsafe_allow_html=True)
            st.divider()
