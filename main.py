import streamlit as st
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
# O ID da Política Comercial (sc) costuma mudar por região. 
# Para POA, tentaremos o sc=2 ou sc=3, mas o ideal é capturar o cookie de localização.
DEFAULT_SC_POA = "1" 

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def buscar_atacadao(termo, sc_param, cookie_texto, qtd_itens=50):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": sc_param  # Canal de Vendas (Loja específica)
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Cookie": cookie_texto # Aqui injetamos a localização (ex: vtex_segment, VTEXSC)
    }
    
    debug_info = {"url": "", "headers_sent": {}, "total_items": 0, "status": None}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_info["url"] = r.url
        debug_info["status"] = r.status_code
        debug_info["headers_sent"] = headers
        
        if r.status_code in [200, 206]:
            data = r.json()
            debug_info["total_items"] = len(data)
            
            lista_final = []
            for produto in data:
                p_id = produto.get('productId')
                p_name = produto.get('productName')
                brand = produto.get('brand', '')
                
                for item in produto.get('items', []):
                    sku_name = item.get('nameComplete') or p_name
                    imagem = item.get('images', [{}])[0].get('imageUrl', '')
                    
                    for seller in item.get('sellers', []):
                        oferta = seller.get('commertialOffer', {})
                        # No Atacadão, AvailableQuantity define se tem na loja de POA
                        estoque = oferta.get('AvailableQuantity', 0)
                        preco = oferta.get('Price', 0)
                        
                        if preco > 0:
                            lista_final.append({
                                "productId": p_id,
                                "productName": sku_name,
                                "brand": brand,
                                "price": preco,
                                "stock": estoque,
                                "image": imagem,
                                "link": produto.get('link', '#')
                            })
                            break
            return lista_final, debug_info
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão POA - Regional", layout="wide")

st.title("🛒 Atacadão - Filtro por Loja (POA)")

with st.sidebar:
    st.header("🛠️ Parâmetros de Localização")
    sc_input = st.text_input("Sales Channel (sc):", value=DEFAULT_SC_POA)
    st.info("Dica: No site do Atacadão, inspecione o 'Network' e procure por 'vtex_segment' nos cookies para POA.")
    cookie_input = st.text_area("Cookie de Sessão (Opcional):", placeholder="Cole aqui o cookie vtex_segment ou VTEXSC...")
    show_debug = st.checkbox("Exibir Debugger de Loja", value=True)

termo = st.text_input("Produto:", value="Arroz Camil")

if termo:
    produtos, debug = buscar_atacadao(termo, sc_input, cookie_input)
    
    if show_debug:
        with st.expander("🔍 DEBUGGER: Parâmetros de Estoque/Loja"):
            st.write(f"**Endpoint Chamado:** `{debug['url']}`")
            st.write(f"**Status da Resposta:** `{debug['status']}`")
            st.write(f"**Total de Produtos na API:** {debug['total_items']}")
            if debug.get('headers_sent'):
                st.write("**Headers enviados:**")
                st.json(debug['headers_sent'])

    if not produtos:
        st.warning("Nenhum item encontrado para esta configuração de loja.")
    else:
        st.success(f"Mostrando {len(produtos)} itens disponíveis na unidade selecionada.")
        
        for idx, p in enumerate(produtos):
            col_img, col_txt, col_btn = st.columns([1, 4, 1])
            with col_img:
                st.image(p['image'], width=80)
            with col_txt:
                st.markdown(f"**{p['productName']}**")
                st.markdown(f"<span style='color:red; font-size:1.2rem; font-weight:bold;'>R$ {p['price']:,.2f}</span>", unsafe_allow_html=True)
                st.caption(f"Marca: {p['brand']} | ID: {p['productId']} | **Estoque: {p['stock']} un**")
            with col_btn:
                st.write("")
                st.link_button("Abrir", p['link'])
            st.divider()
