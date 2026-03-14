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

# --- FUNÇÃO DE BUSCA DEFINITIVA ---
def buscar_atacadao(termo):
    termo_encoded = requests.utils.quote(termo)
    # Endpoint de busca global que ignora mapeamentos de categoria restritos
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search/{termo_encoded}?O=OrderByTopSaleDESC"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        # Range ampliado para garantir que nada fique de fora na primeira página
        "REST-Range": "resources=0-99",
        "Range": "resources=0-99"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code in [200, 206]:
            return r.json()
    except:
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Total", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 12px; border-radius: 10px; 
            margin-bottom: 8px; display: flex; align-items: center; 
            background: #fff;
        }
        .price { color: #d32f2f; font-weight: 800; font-size: 1.1rem; }
        .unit-price { color: #666; font-size: 0.8rem; margin-left: 10px; background: #f9f9f9; padding: 2px 5px; }
        .product-name { font-size: 0.9rem; color: #111; text-decoration: none; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão - Busca Completa")

# Termo fixo inicial conforme solicitado
if "termo_input" not in st.session_state:
    st.session_state.termo_input = "Arroz Camil"

termo = st.text_input("Produto:", value=st.session_state.termo_input)

if termo:
    with st.spinner("Varrendo catálogo..."):
        produtos = buscar_atacadao(termo)
    
    if not produtos:
        st.warning("Nenhum item encontrado.")
    else:
        st.caption(f"Exibindo {len(produtos)} resultados para '{termo}'")
        
        for p in produtos:
            try:
                nome = p.get('productName', '')
                # No Atacadão, um produto pode ter vários itens (SKUs)
                # Vamos focar no primeiro que tiver preço disponível
                item_valido = None
                for item in p.get('items', []):
                    oferta = item.get('sellers', [{}])[0].get('commertialOffer', {})
                    if oferta.get('Price', 0) > 0:
                        item_valido = (item, oferta)
                        break
                
                if not item_valido:
                    continue
                
                sku, info_preco = item_valido
                img = sku.get('images', [{}])[0].get('imageUrl', '')
                preco = info_preco.get('Price', 0)
                link = p.get('link', '#')
                
                _, calc_label = calcular_preco_unidade(nome, preco)
                
                st.markdown(f"""
                    <div class="product-card">
                        <div style="width: 60px; flex-shrink: 0;">
                            <img src="{img}" width="55">
                        </div>
                        <div style="flex-grow: 1; padding-left: 15px;">
                            <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                            <span class="price">R$ {preco:,.2f}</span>
                            {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                        </div>
                        <img src="{LOGO_ATACADAO_URL}" width="35">
                    </div>
                """, unsafe_allow_html=True)
            except:
                continue

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
