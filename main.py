import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"
LOGO_ATACADAO_URL = "https://raw.githubusercontent.com/gymbr/precosmercados/main/logo-atacadao.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES UTILITÁRIAS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- LÓGICA DE BUSCA ATACADÃO ---
def buscar_pagina_atacadao(termo, after=0):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    payload = {
        "operationName": "ProductsQuery",
        "variables": {
            "first": 50,
            "after": str(after),
            "sort": "score_desc",
            "term": termo,
            "selectedFacets": [
                {"key": "region-id", "value": REGION_ID_BASE64},
                {"key": "channel", "value": json.dumps({
                    "salesChannel": "1",
                    "seller": SELLER_ID,
                    "regionId": REGION_ID_BASE64
                })},
                {"key": "locale", "value": "pt-BR"}
            ]
        }
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get('data', {}).get('search', {}).get('products', {})
    except: pass
    return {}

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Atacadão", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div, span, strong, small { font-size: 0.75rem !important; }
        img { max-width: 100px; height: auto; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 600px; margin-left: auto; margin-right: auto; background: transparent;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Atacadão</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    # Centralizado em uma coluna conforme o estilo
    _, col_central, _ = st.columns([1, 4, 1])
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando no Atacadão..."):
        # Busca inicial para pegar o totalCount
        data_inicial = buscar_pagina_atacadao(termo, 0)
        total_itens = data_inicial.get('pageInfo', {}).get('totalCount', 0)
        
        todos_produtos = []
        # Paginação em paralelo (limitado a 4 páginas/200 itens para performance)
        offsets = range(0, min(total_itens, 200), 50)
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(buscar_pagina_atacadao, termo, off) for off in offsets]
            for f in as_completed(futures):
                edges = f.result().get('edges', [])
                for edge in edges:
                    node = edge.get('node', {})
                    # Filtro de relevância simples
                    if all(k in remover_acentos(node.get('name', '')) for k in palavras_chave):
                        todos_produtos.append(node)

    with col_central:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_ATACADAO_URL}" width="120" alt="Atacadão" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 5px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(todos_produtos)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)

        if not todos_produtos:
            st.warning("Nenhum produto encontrado.")

        for p in todos_produtos:
            img = p.get('image', [{}])[0].get('url', DEFAULT_IMAGE_URL)
            nome = p.get('name', 'N/A')
            link = f"https://www.atacadao.com.br{p.get('slug')}/p"
            
            # Lógica de Preços
            offers = p.get('offers', {}).get('offers', [])
            price_varejo = offers[0].get('price', 0.0) if offers else 0.0
            price_atacado = offers[1].get('price') if len(offers) > 1 else None
            
            preco_html = f"<div><b>R$ {price_varejo:,.2f}</b> <small>(Varejo)</small></div>"
            if price_atacado:
                preco_html += f"<div style='color:green;'><b>R$ {price_atacado:,.2f}</b> <small>(Atacado)</small></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{link}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{img}' width='80' style='background-color: white; border-radius: 6px; display: block; border: 1px solid #eee;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'>
                            <a href='{link}' target='_blank' style='text-decoration:none; color:inherit;'><b>{nome}</b></a>
                        </div>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                        <div style='color:gray; font-size:0.7em;'>Marca: {p.get('brand', {}).get('name', 'N/A')}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # Reset de scroll
    components.html(
        f"""<script>
            const cols = window.parent.document.querySelectorAll('[data-testid="stColumn"]');
            cols.forEach(col => col.scrollTop = 0);
        </script>""", height=0
    )
