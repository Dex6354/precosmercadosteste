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
    # Procura por peso ou volume (kg, g, l, ml)
    m = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?|l|litros?|ml)', desc_minus)
    if m:
        try:
            valor = float(m.group(1).replace(',', '.'))
            unidade = m.group(2)
            if unidade in ['g', 'gramas', 'grama', 'ml']:
                valor = valor / 1000
            if valor > 0:
                sufixo = "/L" if 'l' in unidade else "/kg"
                return preco_total / valor, f"R$ {preco_total / valor:.2f}{sufixo}"
        except: pass
    return None, None

# --- FUNÇÃO DE BUSCA COMPLETA ---
def buscar_atacadao_completo(termo):
    # Aumentamos o range para 99 para tentar pegar todo o catálogo daquela busca
    start = 0
    end = 99
    
    # URL com parâmetros explícitos de paginação VTEX
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo}&_from={start}&_to={end}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json",
        "REST-Range": f"resources={start}-{end}",
        "Range": f"resources={start}-{end}"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code in [200, 206]:
            return r.json()
    except:
        pass
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Completo", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 10px; 
            margin-bottom: 10px; display: flex; align-items: center; 
            background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .unit-price { color: #666; font-size: 0.85rem; background: #f1f1f1; padding: 2px 5px; border-radius: 4px; }
        .product-name { font-size: 0.9rem; color: #333; text-decoration: none; font-weight: bold; line-height: 1.1; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

termo_busca = st.text_input("O que deseja buscar?", placeholder="Ex: Arroz, Óleo, Carne...")

if termo_busca:
    with st.spinner(f"Coletando todos os itens de '{termo_busca}'..."):
        produtos = buscar_atacadao_completo(termo_busca)
    
    if not produtos:
        st.warning("Nenhum item retornado. Tente um termo mais simples.")
    else:
        # Mostra a quantidade real retornada pelo JSON
        st.success(f"Foram carregados {len(produtos)} itens.")
        
        # Ordenação automática pelo menor preço
        try:
            produtos = sorted(produtos, key=lambda x: x.get('items', [{}])[0].get('sellers', [{}])[0].get('commertialOffer', {}).get('Price', 9999))
        except: pass

        for p in produtos:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                item = p.get('items', [{}])[0]
                img = item.get('images', [{}])[0].get('imageUrl', '')
                
                oferta = item.get('sellers', [{}])[0].get('commertialOffer', {})
                preco = oferta.get('Price', 0)
                
                if preco > 0:
                    calc_val, calc_label = calcular_preco_unidade(nome, preco)
                    
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="min-width: 70px; text-align: center;">
                                <img src="{img}" width="65" style="max-height: 70px; object-fit: contain;">
                            </div>
                            <div style="flex: 1; margin-left: 12px;">
                                <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                                <span class="price">R$ {preco:,.2f}</span>
                                {f'<span class="unit-price">{calc_label}</span>' if calc_label else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

# Resetar scroll para o topo no Android
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
