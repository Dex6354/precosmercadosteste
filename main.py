import streamlit as st
import requests
import re

# --- CONFIGURAÇÕES ---
# RegionId extraído do seu HAR para a unidade de Poá - SP
REGION_ID_POA = "v3.6358172645391"

def buscar_disponiveis_poa(termo):
    # Usando o endpoint exato que você forneceu
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    params = {
        "ft": termo,
        "sc": "1",
        "regionId": REGION_ID_POA
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code not in [200, 206]:
            return [], []

        data = r.json()
        itens_disponiveis = []
        itens_indisponiveis = [] # Para o debugger

        for produto in data:
            for item in produto.get('items', []):
                for seller in item.get('sellers', []):
                    oferta = seller.get('commertialOffer', {})
                    
                    # CRITÉRIOS DE DISPONIBILIDADE DO ATACADÃO
                    preco = oferta.get('Price', 0)
                    estoque = oferta.get('AvailableQuantity', 0)
                    disponivel_vtex = oferta.get('IsAvailable', False)

                    info_item = {
                        "productId": produto.get('productId'),
                        "productName": item.get('nameComplete'),
                        "brand": produto.get('brand'),
                        "price": preco,
                        "stock": estoque,
                        "link": produto.get('link'),
                        "img": item.get('images', [{}])[0].get('imageUrl', '')
                    }

                    if preco > 0 and estoque > 0 and disponivel_vtex:
                        itens_disponiveis.append(info_item)
                    else:
                        itens_indisponiveis.append(info_item)
                    break 
        
        return itens_disponiveis, itens_indisponiveis
    except:
        return [], []

# --- INTERFACE ---
st.title("🛒 Atacadão - Filtro de Disponibilidade (Poá)")

termo = st.text_input("Pesquisar produto:", value="Arroz Camil")

if termo:
    disponiveis, indisponiveis = buscar_disponiveis_poa(termo)
    
    col1, col2 = st.columns(2)
    col1.metric("Itens Disponíveis", len(disponiveis))
    col2.metric("Itens Ocultados (Sem Estoque)", len(indisponiveis))

    st.subheader("✅ Itens Disponíveis para Compra")
    if not disponiveis:
        st.warning("Nenhum item disponível no momento.")
    else:
        for p in disponiveis:
            with st.container():
                c1, c2, c3 = st.columns([1, 4, 1])
                c1.image(p['img'], width=70)
                c2.markdown(f"**{p['productName']}**")
                c2.markdown(f"<span style='color:red; font-weight:bold;'>R$ {p['price']:,.2f}</span>", unsafe_allow_html=True)
                c2.caption(f"ID: {p['productId']} | Marca: {p['brand']}")
                c3.success(f"Estoque: {p['stock']}")
                c3.link_button("Ver", p['link'])
                st.divider()

    if st.checkbox("Ver itens indisponíveis (Filtro do Site)"):
        st.subheader("❌ Itens que a API retorna mas o site oculta")
        for p in indisponiveis:
            st.caption(f"Indisponível: {p['productName']} (Estoque: {p['stock']} | Preço: R$ {p['price']})")
