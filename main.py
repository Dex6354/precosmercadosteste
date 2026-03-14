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

# --- FUNÇÃO DE BUSCA AJUSTADA ---
def buscar_atacadao(termo, qtd_itens=50):
    # Tratamento do termo para a URL
    termo_encoded = requests.utils.quote(termo)
    # Mudança na estrutura da URL para busca de catálogo mais ampla
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search/{termo_encoded}?O=OrderByTopSaleDESC"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "REST-Range": f"resources=0-{qtd_itens-1}",
        "Range": f"resources=0-{qtd_itens-1}"
    }
    
    debug_info = {"url": url, "status": None, "response_len": 0, "error": None}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        debug_info["status"] = r.status_code
        if r.status_code in [200, 206]:
            data = r.json()
            # Filtragem para garantir que o item tenha preço e pertença à busca
            produtos_validos = []
            for p in data:
                items = p.get('items', [])
                if items:
                    oferta = items[0].get('sellers', [{}])[0].get('commertialOffer', {})
                    if oferta.get('Price', 0) > 0:
                        produtos_validos.append(p)
            
            debug_info["response_len"] = len(produtos_validos)
            return produtos_validos, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Preços", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 12px; 
            margin-bottom: 12px; display: flex; align-items: center; 
            background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.3rem; }
        .unit-price { color: #666; font-size: 0.85rem; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; }
        .product-name { font-size: 1rem; color: #333; text-decoration: none; display: block; margin-bottom: 5px; line-height: 1.2; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

# Fixando a primeira pesquisa em "Arroz Camil" caso o campo esteja vazio
if "primeira_execucao" not in st.session_state:
    st.session_state.termo = "Arroz Camil"
    st.session_state.primeira_execucao = True

col_busca, col_qtd = st.columns([3, 1])
with col_busca:
    termo_busca = st.text_input("Buscar produto:", value=st.session_state.termo, key="input_busca")
with col_qtd:
    qtd_limite = st.selectbox("Qtd Itens", [50, 100, 150], index=0)

enable_debug = st.checkbox("Modo Debugger")

if termo_busca:
    with st.spinner(f"Buscando {termo_busca}..."):
        produtos_raw, info = buscar_atacadao(termo_busca, qtd_limite)
    
    if enable_debug:
        st.info(f"URL: {info['url']} | Itens: {info['response_len']}")
        with st.expander("JSON"):
            st.json(produtos_raw)

    if not produtos_raw:
        st.warning("Nenhum item encontrado. Tente mudar o termo.")
    else:
        for p in produtos_raw:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                item = p['items'][0]
                img = item.get('images', [{}])[0].get('imageUrl', '')
                preco = item['sellers'][0]['commertialOffer'].get('Price', 0)
                
                _, calc_label = calcular_preco_unidade(nome, preco)
                
                st.markdown(f"""
                    <div class="product-card">
                        <div style="min-width: 80px; text-align: center;">
                            <img src="{img}" width="70">
                        </div>
                        <div style="flex: 1; margin-left: 15px;">
                            <a href="{link}" target="_blank" class="product-name"><strong>{nome}</strong></a>
                            <span class="price">R$ {preco:,.2f}</span>
                            {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                        </div>
                        <div style="text-align: right;">
                            <img src="{LOGO_ATACADAO_URL}" width="40">
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            except:
                continue

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
