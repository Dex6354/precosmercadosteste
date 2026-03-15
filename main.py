import streamlit as st
import streamlit.components.v1 as components
import requests
import json
import re

# --- CONFIGURAÇÕES E CONSTANTES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

LOGO_ATACADAO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-atacadao.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÃO AUXILIAR PARA PREÇO POR MEDIDA ---
def extrair_preco_medida(nome, preco):
    """Tenta extrair a quantidade (kg, g, l, ml, un) e calcular o valor unitário."""
    padrao = r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|un|uni|unid)"
    match = re.search(padrao, nome, re.IGNORECASE)
    if match and preco > 0:
        qtd = float(match.group(1).replace(',', '.'))
        unidade = match.group(2).lower()
        
        if unidade == 'g':
            valor = (preco / qtd) * 1000
            return f"R$ {valor:.2f}/kg".replace('.', ',')
        elif unidade == 'ml':
            valor = (preco / qtd) * 1000
            return f"R$ {valor:.2f}/L".replace('.', ',')
        elif unidade in ['kg', 'l', 'un', 'uni', 'unid']:
            valor = preco / qtd
            suffix = 'un' if 'un' in unidade else unidade
            return f"R$ {valor:.2f}/{suffix}".replace('.', ',')
    return ""

# --- LÓGICA DE EXTRAÇÃO (ATACADÃO) ---
def buscar_todos_itens_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    lista_itens = []
    after = 0
    first = 50
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    while True:
        payload = {
            "operationName": "ProductsQuery",
            "variables": {
                "first": first,
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
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            products = data.get('data', {}).get('search', {}).get('products', {}).get('edges', [])
            
            if not products:
                break
            
            for edge in products:
                node = edge.get('node', {})
                offers = node.get('offers', {}).get('offers', [])
                
                price = 0.0
                price_atacado = None
                
                if offers:
                    price = offers[0].get('price', 0.0)
                    if len(offers) > 1:
                        price_atacado = offers[1].get('price')

                lista_itens.append({
                    "productName": node.get('name', 'N/A'),
                    "brand": node.get('brand', {}).get('name', 'N/A'),
                    "price": price,
                    "price_atacado": price_atacado,
                    "link": f"https://www.atacadao.com.br/{node.get('slug')}/p",  # Corrigido: Adicionada a barra
                    "img": node.get('image', [{}])[0].get('url', '')
                })

            total_count = data.get('data', {}).get('search', {}).get('products', {}).get('pageInfo', {}).get('totalCount', 0)
            after += first
            if after >= total_count:
                break
                
        except Exception as e:
            st.error(f"Erro ao processar API: {e}")
            break
            
    return lista_itens

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

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
        .info-cinza { color: gray; font-size: 0.75rem; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 480px; margin-left: auto; margin-right: auto; background: transparent;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados - Atacadão</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, = st.columns([1])

    with st.spinner("🔍 Buscando no mercado..."):
        itens_atacadao = buscar_todos_itens_poa(termo)
        itens_atacadao = sorted(itens_atacadao, key=lambda x: x['price'])

    with col1:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_ATACADAO_URL}" width="80" alt="Atacadão" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(itens_atacadao)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        for p in itens_atacadao:
            img = p['img'] if p.get('img') else DEFAULT_IMAGE_URL
            nome = p['productName']
            preco_normal = p['price']
            preco_atacado = p['price_atacado']
            
            # Cálculo de preço unitário/medida
            medida_info = extrair_preco_medida(nome, preco_normal)
            medida_html = f"<div class='info-cinza'>{medida_info}</div>" if medida_info else ""
            
            if preco_atacado and preco_atacado < preco_normal:
                preco_html = f"<div><b>R$ {preco_normal:.2f}</b> <span class='info-cinza'>(Varejo)</span></div><div><b style='color: green;'>R$ {preco_atacado:.2f}</b> <span class='info-cinza'>(Atacado)</span></div>".replace('.', ',')
            else:
                preco_html = f"<div><b>R$ {preco_normal:.2f}</b></div>".replace('.', ',')

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['link']}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{img}' width='80' style='background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; display: block;'/>
                        <img src='{LOGO_ATACADAO_URL}' width='80' 
                            style='background-color: white; display: block; border-top: 1.5px solid black; border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; padding: 3px;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 2px;'><a href='{p['link']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{nome}</b></a></div>
                        {medida_html}
                        <div style='font-size:0.85em; margin-top:4px;'>{preco_html}</div>
                        <div class='info-cinza' style='margin-top:2px;'>Marca: {p['brand']}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(
        "<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>",
        height=0, width=0
    )
