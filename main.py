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
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?|l|litros?|ml)', desc_minus)
    if m_kg:
        try:
            valor_str = m_kg.group(1).replace(',', '.')
            valor = float(valor_str)
            unidade = m_kg.group(2)
            if unidade in ['g', 'gramas', 'grama', 'ml']:
                valor = valor / 1000
            if valor > 0:
                sufixo = "/L" if 'l' in unidade else "/kg"
                return preco_total / valor, f"R$ {preco_total / valor:.2f}{sufixo}"
        except:
            pass
    return None, None

# --- FUNÇÃO DE BUSCA OTIMIZADA ---
def buscar_atacadao(termo):
    # Usando o parâmetro 'fq' para tentar contornar limites de busca simples
    # E definindo o range de 0 a 49 (máximo seguro antes de causar erro 400 em algumas APIs)
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo}&_from=0&_to=100"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Range": "resources=0-49"
    }
    
    try:
        # Usamos uma sessão para manter cookies básicos se necessário
        session = requests.Session()
        r = session.get(url, headers=headers, timeout=15)
        
        if r.status_code in [200, 206]:
            return r.json()
    except:
        pass
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Preços", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 12px; border-radius: 12px; 
            margin-bottom: 12px; display: flex; align-items: center; 
            background: white; box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.25rem; }
        .unit-price { color: #555; font-size: 0.85rem; background: #f9f9f9; padding: 2px 5px; border-radius: 4px; }
        .product-name { font-size: 0.95rem; color: #222; text-decoration: none; font-weight: 600; line-height: 1.2; display: block; margin-bottom: 4px; }
        .stTextInput > div > div > input { font-size: 16px !important; } /* Evita zoom no iPhone/Android */
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

termo_busca = st.text_input("Buscar produto:", placeholder="Digite o que procura...")

if termo_busca:
    with st.spinner("Buscando no Atacadão..."):
        produtos_raw = buscar_atacadao(termo_busca)
    
    if not produtos_raw:
        st.error("Nenhum item encontrado. Tente pesquisar apenas uma palavra (ex: 'Arroz' em vez de 'Arroz Branco').")
    else:
        st.info(f"Encontrados {len(produtos_raw)} produtos.")
        
        # Ordenar por preço para facilitar a visualização
        try:
            produtos_raw = sorted(produtos_raw, key=lambda x: x.get('items', [{}])[0].get('sellers', [{}])[0].get('commertialOffer', {}).get('Price', 9999))
        except:
            pass

        for p in produtos_raw:
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
                            <div style="min-width: 80px; text-align: center;">
                                <img src="{img}" width="75" style="max-height: 75px; object-fit: contain;">
                            </div>
                            <div style="flex: 1; margin-left: 12px;">
                                <a href="{link}" target="_blank" class="product-name">{nome}</a>
                                <span class="price">R$ {preco:,.2f}</span><br>
                                {f'<span class="unit-price">{calc_label}</span>' if calc_label else ""}
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                continue

# Script para resetar scroll no Android
components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
