import streamlit as st
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
    # Regex melhorada para capturar números com vírgula/ponto e unidades
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
        except: pass
    return None, None

def buscar_atacadao(termo, qtd_itens=50):
    # Mudança estratégica: usar parâmetro 'ft' para busca full-text mais assertiva
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    params = {
        "ft": termo,
        "O": "OrderByTopSaleDESC",
        "_from": 0,
        "_to": qtd_itens - 1
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json"
    }
    
    debug_info = {"url": url, "status": None, "response_len": 0, "error": None}
    
    try:
        # Passando params separadamente para o requests cuidar do encoding
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_info["status"] = r.status_code
        
        if r.status_code in [200, 206]:
            data = r.json()
            produtos_validos = []
            for p in data:
                # Verificação robusta de estoque e preço
                items = p.get('items', [])
                if items:
                    seller = items[0].get('sellers', [{}])[0]
                    oferta = seller.get('commertialOffer', {})
                    if oferta.get('Price', 0) > 0 and oferta.get('AvailableQuantity', 0) > 0:
                        produtos_validos.append(p)
            
            debug_info["response_len"] = len(produtos_validos)
            return produtos_validos, debug_info
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão - Busca", layout="wide")

# Estilo CSS simplificado e funcional
st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 15px; border-radius: 10px; 
            margin-bottom: 10px; display: flex; align-items: center; background: #fff;
        }
        .price { color: #e41e26; font-weight: 800; font-size: 1.2rem; margin-right: 10px; }
        .unit-price { color: #666; font-size: 0.8rem; background: #f5f5f5; padding: 3px 8px; border-radius: 5px; }
    </style>
""", unsafe_allow_html=True)

termo = st.text_input("O que você procura?", value="Arroz Camil")

if termo:
    produtos, info = buscar_atacadao(termo)
    
    if not produtos:
        st.error("Nenhum produto encontrado ou erro na API.")
    else:
        for p in produtos:
            item = p['items'][0]
            nome = p['productName']
            preco = item['sellers'][0]['commertialOffer']['Price']
            img = item['images'][0]['imageUrl']
            link = p['link']
            
            _, label_unidade = calcular_preco_unidade(nome, preco)
            
            st.markdown(f"""
                <div class="product-card">
                    <img src="{img}" width="80" style="margin-right:20px">
                    <div style="flex-grow:1">
                        <div style="font-weight:600; margin-bottom:5px">{nome}</div>
                        <span class="price">R$ {preco:,.2f}</span>
                        {f'<span class="unit-price">{label_unidade}</span>' if label_unidade else ''}
                    </div>
                    <a href="{link}" target="_blank"><button style="cursor:pointer">Ver</button></a>
                </div>
            """, unsafe_allow_html=True)
