import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
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

# --- FUNÇÃO DE BUSCA ---
def buscar_atacadao(termo):
    # Endpoint de busca
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        # Forçando o range de 0 a 49 para trazer 50 itens
        "REST-Range": "resources=0-49",
        "Range": "resources=0-49",
        "x-vtex-api-appkey": "",
        "x-vtex-api-apptoken": ""
    }
    
    debug_info = {"url": url, "status": None, "count": 0}
    
    try:
        # Adicionado allow_redirects e timeout
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        debug_info["status"] = r.status_code
        if r.status_code in [200, 206]:
            data = r.json()
            debug_info["count"] = len(data)
            return data, debug_info
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
            background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.3rem; }
        .unit-price { color: #666; font-size: 0.9rem; }
        .product-name { font-size: 1rem; color: #333; text-decoration: none; display: block; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

enable_debug = st.checkbox("Ver Debugger")
termo_busca = st.text_input("O que você busca?", placeholder="Ex: Banana, Leite...")

if termo_busca:
    with st.spinner("Buscando itens..."):
        produtos_raw, info = buscar_atacadao(termo_busca)
    
    if enable_debug:
        st.write(f"Status: {info['status']} | Itens retornados: {info['count']}")

    if not produtos_raw:
        st.warning("Nada encontrado.")
    else:
        for p in produtos_raw:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                item = p.get('items', [{}])[0]
                img = item.get('images', [{}])[0].get('imageUrl', '')
                
                # Preço
                oferta = item.get('sellers', [{}])[0].get('commertialOffer', {})
                preco = oferta.get('Price', 0)
                
                if preco > 0:
                    calc_val, calc_label = calcular_preco_unidade(nome, preco)
                    
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="min-width: 85px; text-align: center;">
                                <img src="{img}" width="80">
                            </div>
                            <div style="flex: 1; margin-left: 15px;">
                                <a href="{link}" target="_blank" class="product-name"><strong>{nome}</strong></a>
                                <span class="price">R$ {preco:,.2f}</span><br>
                                <span class="unit-price">{calc_label if calc_label else ""}</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

# Resolve problema de cache de scroll no Android
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
