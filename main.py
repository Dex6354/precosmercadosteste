import streamlit as st
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"
REGION_ID_POA = "v3.6358172645391"

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
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": 1,
        "regionId": REGION_ID_POA  # Filtro para a loja de Poá
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code in [200, 206]:
            return r.json()
    except:
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Poá Search", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border-bottom: 1px solid #eee; padding: 15px;
            display: flex; align-items: center; background: white;
        }
        .index-box { font-family: monospace; color: #888; margin-right: 15px; font-size: 1.1rem; }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .details { font-size: 0.8rem; color: #666; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão - Unidade Poá")

termo_busca = st.text_input("Pesquisar:", value="Arroz Camil")

if termo_busca:
    json_data = buscar_atacadao(termo_busca)
    
    if not json_data:
        st.error("Nenhum dado retornado pela API para esta região.")
    else:
        st.success(f"Encontrados {len(json_data)} produtos em Poá.")
        
        for idx, p in enumerate(json_data):
            try:
                p_id = p.get('productId')
                p_name = p.get('productName')
                brand = p.get('brand')
                link = p.get('link', '#')
                ref = p.get('productReference')
                
                item_obj = p['items'][0]
                img = item_obj.get('images', [{}])[0].get('imageUrl', '')
                preco = item_obj.get('sellers', [{}])[0].get('commertialOffer', {}).get('Price', 0)
                
                _, label_un = calcular_preco_unidade(p_name, preco)

                st.markdown(f"""
                    <div class="product-card">
                        <div class="index-box">{idx}:{{</div>
                        <img src="{img}" width="60" style="margin-right:20px">
                        <div style="flex: 1;">
                            <div style="font-weight: bold;">{p_name}</div>
                            <div class="details">
                                "productId": "{p_id}"<br>
                                "brand": "{brand}"<br>
                                "productReference": "{ref}"
                            </div>
                            <div class="price">R$ {preco:,.2f} {f'<span style="font-size:0.8rem; color:gray;">({label_un})</span>' if label_un else ''}</div>
                        </div>
                        <div class="index-box">}}</div>
                        <a href="{link}" target="_blank">
                            <button style="cursor:pointer; background:#d32f2f; color:white; border:none; padding:5px 10px; border-radius:4px;">Ver</button>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.write(f"Erro no item {idx}: {e}")
                continue
