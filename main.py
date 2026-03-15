import streamlit as st
import requests
import re

# --- CONFIGURAÇÕES ---
# Geralmente sc=1 é o padrão, mas a unidade de Poá pode exigir sc=2 ou sc=3 
# dependendo da política comercial. O debugger abaixo ajudará a validar.
SC_POA = "1" 

def buscar_atacadao_poa(termo, sc_param, qtd_itens=50):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": sc_param
    }
    
    # Headers simulando navegação na região de Poá - SP
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Origin": "https://www.atacadao.com.br"
    }
    
    debug_log = {"url": "", "items_count": 0, "status": None}
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        debug_log["url"] = r.url
        debug_log["status"] = r.status_code
        
        if r.status_code in [200, 206]:
            data = r.json()
            debug_log["items_count"] = len(data)
            
            lista_itens = []
            for produto in data:
                brand = produto.get('brand', '')
                p_id = produto.get('productId')
                
                for item in produto.get('items', []):
                    # Captura o estoque específico da unidade (AvailableQuantity)
                    for seller in item.get('sellers', []):
                        oferta = seller.get('commertialOffer', {})
                        estoque = oferta.get('AvailableQuantity', 0)
                        preco = oferta.get('Price', 0)
                        
                        if preco > 0:
                            lista_itens.append({
                                "id": p_id,
                                "nome": item.get('nameComplete', produto.get('productName')),
                                "marca": brand,
                                "preco": preco,
                                "estoque": estoque,
                                "img": item.get('images', [{}])[0].get('imageUrl', ''),
                                "link": produto.get('link', '#')
                            })
                            break
            return lista_itens, debug_log
    except Exception as e:
        return [], {"error": str(e)}
    
    return [], debug_log

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Poá SP", layout="wide")

st.title("🛒 Atacadão - Unidade Poá - SP")

# Sidebar para Debugger e Troca de Loja
with st.sidebar:
    st.header("⚙️ Configurações de Loja")
    sc_selecionado = st.text_input("ID da Loja (sc):", value=SC_POA)
    mostrar_debug = st.checkbox("Ativar Debugger", value=True)
    st.caption("Nota: Se o estoque aparecer 0, tente mudar o ID da Loja para 2 ou 3.")

termo = st.text_input("O que busca em Poá?", value="Arroz Camil")

if termo:
    itens, debug = buscar_atacadao_poa(termo, sc_selecionado)
    
    if mostrar_debug:
        with st.expander("🛠️ Debugger de Localização (Poá)"):
            st.write(f"**URL chamada:** `{debug.get('url')}`")
            st.write(f"**Status da Loja:** {debug.get('status')}")
            st.write(f"**Itens Totais Mapeados:** {len(itens)}")
            if itens:
                st.write("**Exemplo de Estoque Real na Unidade:**")
                st.json(itens[0])

    if not itens:
        st.warning(f"Nenhum item com estoque encontrado em Poá para '{termo}'.")
    else:
        st.info(f"Exibindo {len(itens)} itens encontrados na unidade Poá.")
        
        for p in itens:
            with st.container():
                col1, col2, col3 = st.columns([1, 4, 1])
                with col1:
                    st.image(p['img'], width=80)
                with col2:
                    st.markdown(f"**{p['nome']}**")
                    st.markdown(f"<span style='color:red; font-size:1.1rem; font-weight:bold;'>R$ {p['preco']:,.2f}</span>", unsafe_allow_html=True)
                    st.caption(f"ID: {p['id']} | Marca: {p['marca']}")
                with col3:
                    if p['estoque'] > 0:
                        st.success(f"Estoque: {p['estoque']}")
                    else:
                        st.error("Sem Estoque")
                    st.link_button("Ver", p['link'])
                st.divider()
