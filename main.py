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

# --- FUNÇÕES DE CÁLCULO E FILTRAGEM ---
def calcular_valor_unitario(nome, preco):
    """Retorna o valor numérico do preço por medida para ordenação e a string formatada."""
    padrao = r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|un|uni|unid)"
    match = re.search(padrao, nome, re.IGNORECASE)
    
    if match and preco > 0:
        qtd = float(match.group(1).replace(',', '.'))
        unidade = match.group(2).lower()
        
        if unidade == 'g':
            valor = (preco / qtd) * 1000
            return valor, f"R$ {valor:.2f}/kg".replace('.', ',')
        elif unidade == 'ml':
            valor = (preco / qtd) * 1000
            return valor, f"R$ {valor:.2f}/L".replace('.', ',')
        elif unidade in ['kg', 'l', 'un', 'uni', 'unid']:
            valor = preco / qtd
            suffix = 'un' if 'un' in unidade else unidade
            return valor, f"R$ {valor:.2f}/{suffix}".replace('.', ',')
            
    return float('inf'), ""

def buscar_todos_itens_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    lista_itens = []
    after = 0
    first = 50
    
    # Regex para encontrar a palavra exata (ignora "Elite" ao buscar "Leite")
    # \b representa o limite da palavra
    regex_filtro = re.compile(rf"\b{re.escape(termo)}\b", re.IGNORECASE)

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
                        "salesChannel": "1", "seller": SELLER_ID, "regionId": REGION_ID_BASE64
                    })},
                    {"key": "locale", "value": "pt-BR"}
                ]
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200: break

            data = response.json()
            products = data.get('data', {}).get('search', {}).get('products', {}).get('edges', [])
            if not products: break
            
            for edge in products:
                node = edge.get('node', {})
                nome_produto = node.get('name', '')
                
                # Validação direta: só adiciona se o termo for uma palavra inteira no nome
                if regex_filtro.search(nome_produto):
                    offers = node.get('offers', {}).get('offers', [])
                    price = offers[0].get('price', 0.0) if offers else 0.0
                    price_atacado = offers[1].get('price') if len(offers) > 1 else None
                    
                    val_num, texto_medida = calcular_valor_unitario(nome_produto, price)

                    lista_itens.append({
                        "productName": nome_produto,
                        "brand": node.get('brand', {}).get('name', 'N/A'),
                        "price": price,
                        "price_atacado": price_atacado,
                        "price_unit_val": val_num, 
                        "medida_txt": texto_medida,
                        "link": f"https://www.atacadao.com.br/{node.get('slug')}/p",
                        "img": node.get('image', [{}])[0].get('url', '')
                    })

            total_count = data.get('data', {}).get('search', {}).get('products', {}).get('pageInfo', {}).get('totalCount', 0)
            after += first
            if after >= total_count: break
        except: break
            
    return lista_itens

# --- INTERFACE ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        div, span, strong, small { font-size: 0.75rem !important; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; }
        .product-info { flex: 1 1 auto; min-width: 0; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        .info-cinza { color: gray; font-size: 0.75rem; }
        [data-testid="stColumn"] { overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px; max-width: 480px; margin: auto; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados - Atacadão</h6>", unsafe_allow_html=True)
termo_input = st.text_input("🔎 Digite o nome do produto:", "Leite").strip()

if termo_input:
    col1, = st.columns([1])
    with st.spinner("🔍 Filtrando resultados exatos..."):
        itens = buscar_todos_itens_poa(termo_input)
        itens = sorted(itens, key=lambda x: x['price_unit_val'])

    with col1:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_ATACADAO_URL}' width='80' style='background:white; padding:3px; border-radius:4px;'/></h5>", unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(itens)} itens encontrados para '{termo_input}'</small>", unsafe_allow_html=True)
        
        for p in itens:
            img = p['img'] or DEFAULT_IMAGE_URL
            medida_html = f"<div style='color:#007bff; font-weight:bold;'>{p['medida_txt']}</div>" if p['medida_txt'] else ""
            
            p_normal = f"R$ {p['price']:.2f}".replace('.', ',')
            if p['price_atacado']:
                p_atacado = f"R$ {p['price_atacado']:.2f}".replace('.', ',')
                preco_html = f"<div><b>{p_normal}</b> <span class='info-cinza'>(Varejo)</span></div><div><b style='color:green;'>{p_atacado}</b> <span class='info-cinza'>(Atacado)</span></div>"
            else:
                preco_html = f"<div><b>{p_normal}</b></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['link']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='background:white; border-top-left-radius:6px; border-top-right-radius:6px;'/>
                        <img src='{LOGO_ATACADAO_URL}' width='80' style='background:white; border-top:1.5px solid black; padding:3px;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom:2px;'><a href='{p['link']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{p['productName']}</b></a></div>
                        {medida_html}
                        <div style='margin-top:4px;'>{preco_html}</div>
                        <div class='info-cinza'>Marca: {p['brand']}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0, width=0)
