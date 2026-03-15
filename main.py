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
        "sc": 1 
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    debug_info = {"url": "", "status": None, "json_raw": [], "error": None}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_info["url"] = r.url
        debug_info["status"] = r.status_code
        
        if r.status_code in [200, 206]:
            data = r.json()
            debug_info["json_raw"] = data
            
            lista_final = []
            for produto in data:
                # Cada produto pode ter vários sub-itens (SKUs)
                for item in produto.get('items', []):
                    nome_exibicao = item.get('nameComplete') or produto.get('productName')
                    imagem = item.get('images', [{}])[0].get('imageUrl', '')
                    link = produto.get('link', '#')
                    
                    for seller in item.get('sellers', []):
                        oferta = seller.get('commertialOffer', {})
                        preco = oferta.get('Price', 0)
                        
                        if preco > 0:
                            # Criamos um objeto único para cada variação encontrada
                            lista_final.append({
                                "nome": nome_exibicao,
                                "preco": preco,
                                "imagem": imagem,
                                "link": link
                            })
                            break # Encontrou o preço para este SKU, pula para o próximo SKU
            
            return lista_final, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Resultados Reais", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 12px; border-radius: 12px; 
            margin-bottom: 10px; display: flex; align-items: center; background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .unit-price { color: #666; font-size: 0.8rem; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }
        .product-name { font-size: 0.95rem; color: #333; margin-bottom: 4px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão")

termo_busca = st.text_input("Buscar produto:", value="Arroz Camil")
enable_debug = st.checkbox("Modo Debugger", value=False)

if termo_busca:
    with st.spinner("Buscando todos os itens..."):
        produtos, info = buscar_atacadao(termo_busca)
    
    if enable_debug:
        with st.expander("🛠️ Debugger"):
            st.write(f"Total de ofertas extraídas: {len(produtos)}")
            st.json(info['json_raw'])

    if not produtos:
        st.warning("Nenhum item encontrado.")
    else:
        st.success(f"Exibindo {len(produtos)} resultados encontrados.")
        for p in produtos:
            nome = p['nome']
            preco = p['preco']
            img = p['imagem']
            link = p['link']
            
            _, calc_label = calcular_preco_unidade(nome, preco)
            
            st.markdown(f"""
                <div class="product-card">
                    <img src="{img}" width="70" style="margin-right:15px">
                    <div style="flex: 1;">
                        <div class="product-name">{nome}</div>
                        <span class="price">R$ {preco:,.2f}</span>
                        {f'<span class="unit-price">{calc_label}</span>' if calc_label else ''}
                    </div>
                    <a href="{link}" target="_blank" style="text-decoration:none">
                        <button style="background:#d32f2f; color:white; border:none; padding:8px 12px; border-radius:6px; cursor:pointer">Ver</button>
                    </a>
                </div>
            """, unsafe_allow_html=True)

components.html("<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>", height=0)
