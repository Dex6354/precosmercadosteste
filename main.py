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
    # Regex expandida para capturar quilos, gramas e litros
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
        except:
            pass
    return None, None

def buscar_atacadao(termo, qtd_itens=50):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": 1  # Sales Channel padrão
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    debug_info = {"url": "", "status": None, "recebidos": 0, "filtrados": 0, "json_raw": [], "error": None}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_info["url"] = r.url
        debug_info["status"] = r.status_code
        
        if r.status_code in [200, 206]:
            data = r.json()
            debug_info["json_raw"] = data
            debug_info["recebidos"] = len(data)
            
            produtos_validos = []
            for p in data:
                encontrou_oferta = False
                # Varre todos os SKUs do produto para achar um com preço
                for item in p.get('items', []):
                    for seller in item.get('sellers', []):
                        oferta = seller.get('commertialOffer', {})
                        preco = oferta.get('Price', 0)
                        
                        if preco > 0:
                            # Injeta os dados da oferta válida no objeto principal do produto
                            p['preco_valido'] = preco
                            p['imagem_valida'] = item.get('images', [{}])[0].get('imageUrl', '')
                            produtos_validos.append(p)
                            encontrou_oferta = True
                            break
                    if encontrou_oferta: break
            
            debug_info["filtrados"] = len(produtos_validos)
            return produtos_validos, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Preços Corrigidos", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 12px; border-radius: 12px; 
            margin-bottom: 10px; display: flex; align-items: center; 
            background: white; transition: 0.3s;
        }
        .product-card:hover { border-color: #d32f2f; box-shadow: 0 4px 8px rgba(0,0,0,0.05); }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .unit-price { color: #666; font-size: 0.8rem; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }
        .product-name { font-size: 0.95rem; color: #333; margin-bottom: 4px; font-weight: 500; }
        .btn-ver { background: #d32f2f; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; text-decoration: none; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

# Inicialização de busca padrão
if "termo" not in st.session_state:
    st.session_state.termo = "Arroz Camil"

col_busca, col_debug = st.columns([3, 1])
with col_busca:
    termo_busca = st.text_input("Buscar produto:", value=st.session_state.termo)
with col_debug:
    enable_debug = st.checkbox("Modo Debugger", value=True)

if termo_busca:
    with st.spinner(f"Buscando {termo_busca}..."):
        produtos, info = buscar_atacadao(termo_busca)
    
    if enable_debug:
        with st.expander("🛠️ Painel de Controle de API"):
            st.code(f"URL: {info['url']}")
            st.write(f"**Recebidos no JSON:** {info['recebidos']} | **Válidos com Preço:** {info['filtrados']}")
            if info['error']: st.error(info['error'])
            st.json(info['json_raw'])

    if not produtos:
        st.warning("Nenhum item com preço encontrado para este termo.")
    else:
        st.success(f"Encontrados {len(produtos)} itens.")
        for p in produtos:
            nome = p.get('productName', '')
            link = p.get('link', '#')
            img = p.get('imagem_valida', '')
            preco = p.get('preco_valido', 0)
            
            _, calc_label = calcular_preco_unidade(nome, preco)
            
            st.markdown(f"""
                <div class="product-card">
                    <div style="min-width: 70px; text-align: center;">
                        <img src="{img}" width="60">
                    </div>
                    <div style="flex: 1; margin-left: 15px;">
                        <div class="product-name">{nome}</div>
                        <span class="price">R$ {preco:,.2f}</span>
                        {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                    </div>
                    <div style="text-align: right;">
                        <a href="{link}" target="_blank" class="btn-ver">Ver no Site</a>
                    </div>
                </div>
            """, unsafe_allow_html=True)

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
