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

# --- FUNÇÃO DE BUSCA CORRIGIDA ---
def buscar_atacadao(termo, qtd_itens=50):
    # Usando a URL exata que você validou
    termo_encoded = requests.utils.quote(termo)
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search/{termo_encoded}?O=OrderByTopSaleDESC"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Range": f"resources=0-{qtd_itens-1}"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code in [200, 206]:
            return r.json(), {"status": r.status_code, "url": url}
    except Exception as e:
        return [], {"error": str(e)}
    
    return [], {"status": r.status_code}

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Todos os Itens", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 15px; border-radius: 10px; 
            margin-bottom: 10px; display: flex; align-items: center; 
            background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .price { color: #d32f2f; font-weight: 800; font-size: 1.2rem; }
        .unit-price { color: #777; font-size: 0.8rem; margin-left: 10px; border-left: 1px solid #ccc; padding-left: 10px; }
        .product-name { font-size: 0.95rem; color: #222; text-decoration: none; font-weight: 600; line-height: 1.1; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

# Fixando a primeira pesquisa
if "termo" not in st.session_state:
    st.session_state.termo = "Arroz Camil"

termo_busca = st.text_input("Buscar produto:", value=st.session_state.termo)

if termo_busca:
    with st.spinner(f"Carregando todos os itens para '{termo_busca}'..."):
        produtos, info = buscar_atacadao(termo_busca)
    
    if not produtos:
        st.error("Nenhum item retornado pela API.")
    else:
        st.caption(f"Encontrados {len(produtos)} itens.")
        
        for p in produtos:
            try:
                # Extração segura de dados
                nome = p.get('productName', 'Sem nome')
                link = p.get('link', '#')
                
                # Acessando o primeiro SKU (item) e a primeira oferta (seller)
                item = p['items'][0]
                img = item['images'][0]['imageUrl']
                oferta = item['sellers'][0]['commertialOffer']
                preco = oferta.get('Price', 0)
                
                # Se o preço for 0, o item pode estar indisponível, mas vamos mostrar se existir
                calc_val, calc_label = calcular_preco_unidade(nome, preco)
                
                st.markdown(f"""
                    <div class="product-card">
                        <div style="width: 80px; flex-shrink: 0;">
                            <img src="{img}" width="70" style="object-fit: contain;">
                        </div>
                        <div style="flex-grow: 1; padding: 0 15px;">
                            <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                            <span class="price">R$ {preco:,.2f}</span>
                            {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                        </div>
                        <div style="width: 40px;">
                            <img src="{LOGO_ATACADAO_URL}" width="40">
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            except (KeyError, IndexError):
                continue

# Resetar scroll
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
