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
            
            # Percorre cada PRODUTO retornado (Ex: ID 25614)
            for produto in data:
                p_id = produto.get('productId')
                p_name = produto.get('productName')
                brand = produto.get('brand', '')
                link = produto.get('link', '#')
                
                # Percorre cada SKU/ITEM dentro desse produto
                for item in produto.get('items', []):
                    # Captura detalhes específicos do item
                    sku_name = item.get('nameComplete') or p_name
                    imagem = item.get('images', [{}])[0].get('imageUrl', '')
                    
                    # Percorre os vendedores para achar o preço
                    for seller in item.get('sellers', []):
                        oferta = seller.get('commertialOffer', {})
                        preco = oferta.get('Price', 0)
                        
                        if preco > 0:
                            # CRIA UM ITEM INDEPENDENTE NA LISTA
                            lista_final.append({
                                "productId": p_id,
                                "productName": sku_name,
                                "brand": brand,
                                "price": preco,
                                "image": imagem,
                                "link": link
                            })
                            # Passa para o próximo SKU após achar o preço deste
                            break 
            
            return lista_final, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Coletor Completo", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border: 1px solid #eee; padding: 12px; border-radius: 12px; 
            margin-bottom: 10px; display: flex; align-items: center; background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .unit-price { color: #666; font-size: 0.8rem; background: #f0f0f0; padding: 2px 6px; border-radius: 4px; margin-left: 10px; }
        .product-name { font-size: 0.95rem; color: #333; margin-bottom: 4px; font-weight: 600; }
        .brand-badge { font-size: 0.7rem; background: #333; color: white; padding: 2px 6px; border-radius: 4px; margin-right: 8px; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão - Busca por Item")

termo_busca = st.text_input("O que deseja pesquisar?", value="Arroz Camil")
enable_debug = st.checkbox("Ver Debugger (JSON)", value=False)

if termo_busca:
    with st.spinner("Processando todos os itens da API..."):
        produtos, info = buscar_atacadao(termo_busca)
    
    if enable_debug:
        with st.expander("🛠️ Detalhes da Requisição"):
            st.write(f"Total de itens individuais mapeados: {len(produtos)}")
            st.json(info['json_raw'])

    if not produtos:
        st.warning("Nenhum item com preço disponível encontrado.")
    else:
        st.success(f"Encontrados {len(produtos)} itens.")
        
        for idx, p in enumerate(produtos):
            nome = p['productName']
            preco = p['price']
            img = p['image']
            link = p['link']
            marca = p['brand']
            p_id = p['productId']
            
            _, calc_label = calcular_preco_unidade(nome, preco)
            
            st.markdown(f"""
                <div class="product-card">
                    <div style="font-size: 0.7rem; color: #999; margin-right: 10px; width: 20px;">{idx}</div>
                    <img src="{img}" width="65" style="margin-right:15px">
                    <div style="flex: 1;">
                        <div style="margin-bottom: 4px;">
                            <span class="brand-badge">{marca}</span>
                            <span style="font-size: 0.7rem; color: #999;">ID: {p_id}</span>
                        </div>
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
