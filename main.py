import streamlit as st
import requests
import unicodedata
import re
import json

# --- CONFIGURAÇÕES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?|l|litros?|ml)', desc_minus)
    if m_kg:
        try:
            valor = float(m_kg.group(1).replace(',', '.'))
            unidade = m_kg.group(2)
            if unidade in ['g', 'grama', 'gramas', 'ml']:
                valor /= 1000
            if valor > 0:
                preco_un = preco_total / valor
                sufixo = "/kg" if unidade[0] in ['k', 'g'] else "/L"
                return preco_un, f"R$ {preco_un:.2f}{sufixo}"
        except: pass
    return None, None

def buscar_atacadao(termo, qtd_itens=50):
    # Endpoint ajustado para busca mais ampla (Simulando o comportamento do site)
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    # Parâmetros que forçam a busca a ignorar filtros restritivos de categoria
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": 1  # Sales Channel 1 (Geralmente o padrão para e-commerce)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    debug_data = {
        "url_solicitada": "",
        "status_code": None,
        "total_recebido": 0,
        "total_filtrado": 0,
        "json_raw": [],
        "erro": None
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_data["url_solicitada"] = r.url
        debug_data["status_code"] = r.status_code
        
        if r.status_code in [200, 206]:
            data = r.json()
            debug_data["json_raw"] = data
            debug_data["total_recebido"] = len(data)
            
            produtos_validos = []
            for p in data:
                items = p.get('items', [])
                if items:
                    # O site do Atacadão às vezes retorna itens sem preço ou indisponíveis
                    # Removemos a trava de 'AvailableQuantity' se quiser ver TUDO (mesmo sem estoque)
                    seller = items[0].get('sellers', [{}])[0]
                    oferta = seller.get('commertialOffer', {})
                    
                    if oferta.get('Price', 0) > 0:
                        produtos_validos.append(p)
            
            debug_data["total_filtrado"] = len(produtos_validos)
            return produtos_validos, debug_data
        else:
            debug_data["erro"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_data["erro"] = str(e)
    
    return [], debug_data

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Debugger", layout="wide")

st.markdown("""
    <style>
        .product-card { border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-bottom: 8px; display: flex; align-items: center; background: white; }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.1rem; }
        .unit-price { color: #666; font-size: 0.8rem; background: #f0f0f0; padding: 2px 5px; border-radius: 4px; margin-left: 10px;}
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão - Busca Corrigida")

col1, col2 = st.columns([3, 1])
with col1:
    termo_busca = st.text_input("Buscar produto:", value="Arroz Camil")
with col2:
    enable_debug = st.checkbox("Ativar Debugger", value=True)

if termo_busca:
    with st.spinner("Buscando..."):
        produtos, debug = buscar_atacadao(termo_busca)

    if enable_debug:
        with st.expander("🛠️ PAINEL DE DEBUG"):
            st.write(f"**URL chamada:** `{debug['url_solicitada']}`")
            st.write(f"**Status:** {debug['status_code']}")
            st.write(f"**Itens que a API enviou:** {debug['total_recebido']}")
            st.write(f"**Itens após filtro de preço:** {debug['total_filtrado']}")
            if debug['erro']: st.error(debug['erro'])
            st.json(debug['json_raw'])

    if not produtos:
        st.warning("Nenhum item válido encontrado.")
    else:
        st.success(f"Exibindo {len(produtos)} produtos encontrados.")
        for p in produtos:
            item = p['items'][0]
            nome = p['productName']
            preco = item['sellers'][0]['commertialOffer']['Price']
            img = item['images'][0]['imageUrl']
            
            _, label_un = calcular_preco_unidade(nome, preco)
            
            st.markdown(f"""
                <div class="product-card">
                    <img src="{img}" width="60" style="margin-right:15px">
                    <div style="flex:1">
                        <div style="font-size:0.9rem;">{nome}</div>
                        <span class="price">R$ {preco:,.2f}</span>
                        {f'<span class="unit-price">{label_un}</span>' if label_un else ''}
                    </div>
                </div>
            """, unsafe_allow_html=True)
