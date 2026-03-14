import streamlit as st
import streamlit.components.v1 as components
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
    # Tenta encontrar KG ou Gramas para calcular valor relativo
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?)', desc_minus)
    if m_kg:
        try:
            valor_str = m_kg.group(1).replace(',', '.')
            valor = float(valor_str)
            unidade = m_kg.group(2)
            if 'g' in unidade and 'kg' not in unidade:
                valor = valor / 1000
            if valor > 0:
                return preco_total / valor, f"R$ {preco_total / valor:.2f}/kg"
        except:
            pass
    return None, None

# --- FUNÇÃO DE BUSCA AJUSTADA ---
def buscar_atacadao(termo):
    # Endpoint de busca pública VTEX
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json",
        "REST-Range": "resources=0-49", # Define o intervalo para evitar Erro 206
        "Range": "resources=0-49"      # Alguns servidores exigem este formato
    }
    
    debug_info = {"url": url, "status": None, "response_len": 0, "error": None}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        debug_info["status"] = r.status_code
        if r.status_code in [200, 206]:
            data = r.json()
            debug_info["response_len"] = len(data)
            return data, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 12px; 
            margin-bottom: 12px; display: flex; align-items: center; 
            background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.3rem; }
        .unit-price { color: #666; font-size: 0.9rem; }
        .product-name { font-size: 1rem; color: #333; text-decoration: none; display: block; margin-bottom: 5px; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

enable_debug = st.checkbox("Modo Debugger")
termo_busca = st.text_input("Buscar produto:", placeholder="Ex: Arroz, Feijão...")

if termo_busca:
    with st.spinner("Buscando..."):
        produtos_raw, info = buscar_atacadao(termo_busca)
    
    if enable_debug:
        st.info(f"Status: {info['status']} | Itens: {info['response_len']}")
        if info['error']: st.error(info['error'])
        with st.expander("Dados crus (JSON)"):
            st.json(produtos_raw)

    if not produtos_raw:
        st.warning("Nenhum item encontrado. Tente um termo mais genérico.")
    else:
        for p in produtos_raw:
            try:
                nome = p.get('productName', 'Produto sem nome')
                link = p.get('link', '#')
                
                # Navegação no JSON da VTEX para pegar imagem e preço
                items = p.get('items', [])
                if not items: continue
                
                primeiro_item = items[0]
                img = primeiro_item.get('images', [{}])[0].get('imageUrl', '')
                
                sellers = primeiro_item.get('sellers', [])
                if not sellers: continue
                
                oferta = sellers[0].get('commertialOffer', {})
                preco = oferta.get('Price', 0)
                
                # Só exibe se houver preço
                if preco > 0:
                    calc_val, calc_label = calcular_preco_unidade(nome, preco)
                    
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="min-width: 90px; text-align: center;">
                                <img src="{img}" width="80" style="object-fit: contain;">
                            </div>
                            <div style="flex: 1; margin-left: 15px;">
                                <a href="{link}" target="_blank" class="product-name"><strong>{nome}</strong></a>
                                <span class="price">R$ {preco:,.2f}</span><br>
                                <span class="unit-price">{calc_label if calc_label else ""}</span>
                            </div>
                            <div style="text-align: right;">
                                <img src="{LOGO_ATACADAO_URL}" width="50">
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

# Forçar rolagem ao topo ao pesquisar
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
