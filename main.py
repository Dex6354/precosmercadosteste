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

def buscar_atacadao(termo):
    # Endpoint via Search API (Intelligent Search)
    url = f"https://www.atacadao.com.br/api/v1/search?q={termo}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.atacadao.com.br/"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get('products', [])
    except:
        pass
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão App", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 12px; 
            margin-bottom: 12px; display: flex; align-items: center; background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.3rem; }
        .unit-price { color: #666; font-size: 0.85rem; background: #f1f1f1; padding: 2px 5px; border-radius: 4px; }
        .product-name { font-size: 1rem; color: #333; text-decoration: none; font-weight: bold; line-height: 1.2; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

termo_busca = st.text_input("O que você busca?", placeholder="Ex: Arroz")

if termo_busca:
    with st.spinner("Buscando..."):
        produtos = buscar_atacadao(termo_busca)
    
    if not produtos:
        st.error("Nenhum item encontrado. Tente um termo mais simples como 'Feijao' ou 'Leite'.")
    else:
        st.success(f"{len(produtos)} itens encontrados.")
        
        for p in produtos:
            try:
                nome = p.get('productName', '')
                link = p.get('link', '#')
                # Na API v1, a imagem e preço ficam em 'items'
                item_detalhe = p.get('items', [{}])[0]
                img = item_detalhe.get('images', [{}])[0].get('imageUrl', '')
                
                # Captura de preço na API v1 (costuma vir em centavos ou direto em Price)
                oferta = item_detalhe.get('sellers', [{}])[0].get('commertialOffer', {})
                preco = oferta.get('Price', 0)
                
                if preco > 0:
                    calc_val, calc_label = calcular_preco_unidade(nome, preco)
                    
                    st.markdown(f"""
                        <div class="product-card">
                            <div style="min-width: 80px; text-align: center;">
                                <img src="{img}" width="75" style="max-height: 80px; object-fit: contain;">
                            </div>
                            <div style="flex: 1; margin-left: 15px;">
                                <a href="https://www.atacadao.com.br{link}" target="_blank" class="product-name">{nome}</a><br>
                                <span class="price">R$ {preco:,.2f}</span>
                                {f'<br><span class="unit-price">{calc_label}</span>' if calc_label else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
