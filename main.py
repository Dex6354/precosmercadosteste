import streamlit as st
import requests
import json

# --- CONFIGURAÇÕES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

def buscar_todos_produtos_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    
    itens_disponiveis = []
    itens_indisponiveis = []
    
    # Controle de paginação
    items_per_page = 20
    current_after = 0
    tem_mais_paginas = True

    while tem_mais_paginas:
        payload = {
            "operationName": "ProductsQuery",
            "variables": {
                "first": items_per_page,
                "after": str(current_after),
                "sort": "score_desc",
                "term": termo,
                "selectedFacets": [
                    {"key": "region-id", "value": REGION_ID_BASE64},
                    {"key": "channel", "value": json.dumps({
                        "salesChannel": "1",
                        "seller": SELLER_ID,
                        "regionId": REGION_ID_BASE64
                    })},
                    {"key": "locale", "value": "pt-BR"}
                ]
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            search_data = data.get('data', {}).get('search', {})
            products_edges = search_data.get('products', {}).get('edges', [])
            
            # Se não retornar mais itens, para o loop
            if not products_edges:
                tem_mais_paginas = False
                break

            for edge in products_edges:
                node = edge.get('node', {})
                skus = node.get('skus', [])
                if not skus: continue
                
                offer = skus[0].get('offers', {}).get('offers', [{}])[0]
                price = offer.get('price', 0)
                availability = offer.get('availability', "")
                is_in_stock = "InStock" in availability 

                info_item = {
                    "productId": node.get('id'),
                    "productName": node.get('name'),
                    "brand": node.get('brand', {}).get('name', 'N/A'),
                    "price": price,
                    "link": f"https://www.atacadao.com.br{node.get('slug')}/p",
                    "img": node.get('image', [{}])[0].get('url', '') if node.get('image') else '',
                    "stock_status": availability
                }

                if price > 0 and is_in_stock:
                    itens_disponiveis.append(info_item)
                else:
                    itens_indisponiveis.append(info_item)

            # Verifica se chegamos ao fim com base no total de produtos
            total_count = search_data.get('products', {}).get('pageInfo', {}).get('totalCount', 0)
            current_after += items_per_page
            
            if current_after >= total_count:
                tem_mais_paginas = False

        except Exception as e:
            st.error(f"Erro na requisição: {e}")
            break
            
    return itens_disponiveis, itens_indisponiveis

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão Poá - Full Search", layout="wide")
st.title("🛒 Atacadão - Busca Completa (Poá)")

termo = st.text_input("Pesquisar produto:", value="Banana")

if termo:
    with st.spinner(f"Buscando todos os itens para '{termo}'..."):
        disponiveis, indisponiveis = buscar_todos_produtos_poa(termo)
    
    col1, col2 = st.columns(2)
    col1.metric("Itens Disponíveis", len(disponiveis))
    col2.metric("Total Encontrado (incluindo ocultos)", len(disponiveis) + len(indisponiveis))

    st.subheader(f"✅ Resultados para '{termo}'")
    if not disponiveis:
        st.warning("Nenhum item com estoque encontrado.")
    else:
        for p in disponiveis:
            with st.container():
                c1, c2, c3 = st.columns([1, 4, 1])
                if p['img']:
                    c1.image(p['img'], width=80)
                c2.markdown(f"**{p['productName']}**")
                c2.markdown(f"<span style='color:green; font-size:20px; font-weight:bold;'>R$ {p['price']:,.2f}</span>", unsafe_allow_html=True)
                c2.caption(f"Marca: {p['brand']} | ID: {p['productId']}")
                c3.link_button("Ir para o Site", p['link'])
                st.divider()

    if st.checkbox("Mostrar Itens Sem Estoque"):
        for p in indisponiveis:
            st.text(f"Sem estoque: {p['productName']} - Status: {p['stock_status']}")
