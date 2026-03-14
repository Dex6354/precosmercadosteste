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
    # Busca padrões de peso/volume: kg, g, l, ml
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

# --- FUNÇÃO DE BUSCA DIRETA ---
def buscar_atacadao(termo):
    # Utilizando o endpoint /io/api/ conforme identificado
    url = f"https://www.atacadao.com.br/io/api/catalog_system/pub/products/search?ft={termo}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão Direto", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 10px; 
            margin-bottom: 10px; display: flex; align-items: center; 
            background: white; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .unit-price { color: #666; font-size: 0.85rem; background: #f1f1f1; padding: 2px 5px; border-radius: 4px; }
        .product-name { font-size: 0.95rem; color: #333; text-decoration: none; font-weight: bold; line-height: 1.2; }
        input { font-size: 16px !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

termo_busca = st.text_input("Buscar produto:", placeholder="Ex: Arroz, Feijão...")

if termo_busca:
    with st.spinner("Carregando itens do Atacadão..."):
        produtos = buscar_atacadao(termo_busca)
    
    if not produtos:
        st.warning("Nenhum item encontrado no JSON.")
    else:
        st.success(f"{len(produtos)} itens carregados com sucesso.")
        
        # Ordenação por preço
        try:
            produtos = sorted(produtos, key=lambda x: x.get('items', [{}])[0].get('sellers', [{}])[0].get('commertialOffer', {}).get('Price', 9999))
        except: pass

        for p in produtos:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                item_detalhe = p.get('items', [{}])[0]
                img = item_detalhe.get('images', [{}])[0].get('imageUrl', '')
                
                oferta = item_detalhe.get('sellers', [{}])[0].get('commertialOffer', {})
                preco = oferta.get('Price', 0)
                
                if preco > 0:
                    calc_val, calc_label = calcular_preco_unidade(nome, preco)
                    
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="min-width: 75px; text-align: center;">
                                <img src="{img}" width="70" style="max-height: 75px; object-fit: contain;">
                            </div>
                            <div style="flex: 1; margin-left: 12px;">
                                <a href="{link}" target="_blank" class="product-name">{nome}</a><br>
                                <span class="price">R$ {preco:,.2f}</span>
                                {f'<br><span class="unit-price">{calc_label}</span>' if calc_label else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

# Scroll para o topo
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
