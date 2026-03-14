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

# --- FUNÇÃO DE BUSCA REVISADA ---
def buscar_atacadao(termo):
    termo_encoded = requests.utils.quote(termo)
    # Endpoint alternativo mais estável
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo_encoded}&O=OrderByTopSaleDESC"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Range": "resources=0-49",
        "Origin": "https://www.atacadao.com.br",
        "Referer": "https://www.atacadao.com.br/"
    }
    
    try:
        # Usando Session para manter headers consistentes
        session = requests.Session()
        r = session.get(url, headers=headers, timeout=15)
        
        if r.status_code in [200, 206]:
            return r.json()
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Comparador Total", layout="wide")

# CSS para cards compactos
st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 10px; border-radius: 8px; 
            margin-bottom: 8px; display: flex; align-items: center; 
            background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.1rem; }
        .unit-price { color: #555; font-size: 0.8rem; margin-left: 10px; border-left: 1px solid #eee; padding-left: 10px;}
        .product-name { font-size: 0.85rem; color: #333; text-decoration: none; font-weight: 600; line-height: 1.2; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

# Fixando Arroz Camil na primeira pesquisa
if "termo_fixo" not in st.session_state:
    st.session_state.termo_fixo = "Arroz Camil"

termo_busca = st.text_input("Pesquisar produto:", value=st.session_state.termo_fixo)

if termo_busca:
    with st.spinner(f"Buscando todos os itens para '{termo_busca}'..."):
        produtos = buscar_atacadao(termo_busca)
    
    if not produtos:
        st.warning("A API não retornou dados. Tente novamente em instantes.")
    else:
        st.success(f"Foram encontrados {len(produtos)} itens.")
        
        for p in produtos:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                
                # O Atacadão as vezes retorna itens sem preço no primeiro slot
                # Varremos os itens para achar o que tem valor
                dados_item = None
                for item in p.get('items', []):
                    seller = item.get('sellers', [{}])[0]
                    preco = seller.get('commertialOffer', {}).get('Price', 0)
                    if preco > 0:
                        dados_item = {
                            "img": item.get('images', [{}])[0].get('imageUrl', ''),
                            "preco": preco
                        }
                        break
                
                if not dados_item: continue
                
                _, calc_label = calcular_preco_unidade(nome, dados_item['preco'])
                
                st.markdown(f"""
                    <div class="product-card">
                        <div style="width: 60px; text-align: center;">
                            <img src="{dados_item['img']}" width="50" style="max-height: 50px; object-fit: contain;">
                        </div>
                        <div style="flex: 1; margin-left: 15px;">
                            <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                            <span class="price">R$ {dados_item['preco']:,.2f}</span>
                            {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                        </div>
                        <div style="text-align: right;">
                            <img src="{LOGO_ATACADAO_URL}" width="35">
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            except:
                continue

# Scroll para o topo
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
