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

# --- FUNÇÃO DE BUSCA COM LOCALIZAÇÃO ---
def buscar_atacadao(termo, segment_token=None):
    termo_encoded = requests.utils.quote(termo)
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo_encoded}&O=OrderByTopSaleDESC"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Range": "resources=0-99",
        "Origin": "https://www.atacadao.com.br",
        "Referer": "https://www.atacadao.com.br/"
    }
    
    # Se tivermos o token da loja (Poá), injetamos no Cookie
    cookies = {}
    if segment_token:
        cookies["vtex_segment"] = segment_token

    try:
        r = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        if r.status_code in [200, 206]:
            return r.json(), r.status_code
    except Exception as e:
        return [], str(e)
    return [], r.status_code

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Debugger - Poá", layout="wide")

# Sidebar - Painel de Debugger
st.sidebar.title("🛠️ Debugger de Loja")
loja_selecionada = st.sidebar.selectbox("Selecionar Unidade:", ["Geral (Brasil)", "Poá - SP"])

# Token aproximado para a região de Poá (baseado em geocoordinates padrão da VTEX para SP)
token_poa = "eyJjYW1wYWlnblRhZ3MiOltdLCJjaGVja291dFJlZ2lvbiI6bnVsbCwiY3VycmVuY3lDb2RlIjoiQlJMIiwiY3VycmVuY3lTeW1ib2wiOiJSJCIsImNvdW50cnlDb2RlIjoiQlJBIiwiY3VsdHVyZUluZm8iOiJwdC1CUiIsImRyaXZlSWQiOm51bGwsImV0YWciOm51bGwsImZhY2V0cyI6bnVsbCwiZmlsdGVycyI6bnVsbCwibG9jYWxlIjoicHQtQlIiLCJtYXJrZXRpbmdDb250ZXh0IjpudWxsLCJwcmVjZUluaGVyaXRhbmNlU3RyYXRlZ3kiOiJwcmlvcmV0aXplLWxvd2VzdC1wcmljZSIsInJlZ2lvbklkIjpudWxsLCJzZWdtZW50VG9rZW4iOiIiLCJ1dG1fY2FtcGFpZ24iOm51bGwsInV0bV9tZWRpdW0iOm51bGwsInV0bV9zb3VyY2UiOm51bGwsInV0bWlfY2FtcGFpZ24iOm51bGwsInV0bWlfY3AiOm51bGwsInV0bWlfcGFnZSI6bnVsbH0"

token_atual = token_poa if loja_selecionada == "Poá - SP" else None

if st.sidebar.checkbox("Visualizar Headers JSON"):
    st.sidebar.write("Cookie Token:", token_atual)

# Estilo
st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 10px; border-radius: 8px; 
            margin-bottom: 8px; display: flex; align-items: center; background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.1rem; }
        .unit-price { color: #555; font-size: 0.8rem; margin-left: 10px; border-left: 1px solid #eee; padding-left: 10px;}
        .product-name { font-size: 0.85rem; color: #333; font-weight: 600; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

st.title(f"🛒 Atacadão - Unidade: {loja_selecionada}")

# Termo fixo
if "search_val" not in st.session_state:
    st.session_state.search_val = "Arroz Camil"

termo = st.text_input("Pesquisar:", value=st.session_state.search_val)

if termo:
    with st.spinner(f"Consultando estoque em {loja_selecionada}..."):
        produtos, status = buscar_atacadao(termo, token_atual)
    
    if not produtos:
        st.warning(f"Sem resultados para '{termo}' nesta unidade. (Status: {status})")
    else:
        st.info(f"Sucesso! {len(produtos)} itens encontrados.")
        
        for p in produtos:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                
                # Busca o SKU com preço ativo
                melhor_oferta = None
                for item in p.get('items', []):
                    oferta = item.get('sellers', [{}])[0].get('commertialOffer', {})
                    if oferta.get('Price', 0) > 0:
                        melhor_oferta = {"img": item['images'][0]['imageUrl'], "preco": oferta['Price']}
                        break
                
                if not melhor_oferta: continue
                
                _, calc_label = calcular_preco_unidade(nome, melhor_oferta['preco'])
                
                st.markdown(f"""
                    <div class="product-card">
                        <div style="width: 60px; text-align: center;">
                            <img src="{melhor_oferta['img']}" width="50">
                        </div>
                        <div style="flex: 1; margin-left: 15px;">
                            <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                            <span class="price">R$ {melhor_oferta['preco']:,.2f}</span>
                            {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                        </div>
                        <div style="opacity: 0.5; font-size: 0.7rem;">ID: {p.get('productId')}</div>
                    </div>
                """, unsafe_allow_html=True)
            except:
                continue

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
