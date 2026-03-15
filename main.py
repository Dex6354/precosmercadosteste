import streamlit as st
import requests
import json

# --- CONFIGURAÇÕES ---
# Region ID e Seller extraídos dos seus parâmetros
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

def buscar_disponiveis_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    
    # Payload baseado nos parâmetros que você forneceu
    payload = {
        "operationName": "ProductsQuery",
        "variables": {
            "first": 20,
            "after": "0",
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
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if response.status_code != 200:
            return [], []

        data = response.json()
        # Navegando na estrutura GraphQL: data -> search -> products -> edges
        products_edges = data.get('data', {}).get('search', {}).get('products', {}).get('edges', [])
        
        itens_disponiveis = []
        itens_indisponiveis = []

        for edge in products_edges:
            node = edge.get('node', {})
            
            # No GraphQL do Atacadão, o preço e estoque geralmente ficam em offers
            # Tentando extrair do primeiro item/sku disponível
            sku = node.get('skus', [{}])[0]
            offer = sku.get('offers', {}).get('offers', [{}])[0]
            
            price = offer.get('price', 0)
            availability = offer.get('availability', "")
            # "http://schema.org/InStock" é o padrão comum de disponibilidade
            is_in_stock = "InStock" in availability 

            info_item = {
                "productId": node.get('id'),
                "productName": node.get('name'),
                "brand": node.get('brand', {}).get('name', 'N/A'),
                "price": price,
                "link": f"https://www.atacadao.com.br{node.get('slug')}/p",
                "img": node.get('image', [{}])[0].get('url', ''),
                "stock_status": availability
            }

            if price > 0 and is_in_stock:
                itens_disponiveis.append(info_item)
            else:
                itens_indisponiveis.append(info_item)
        
        return itens_disponiveis, itens_indisponiveis
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return [], []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão Poá - GraphQL", layout="wide")
st.title("🛒 Atacadão - Filtro GraphQL (Poá)")

termo = st.text_input("Pesquisar produto:", value="Arroz Camil")

if termo:
    disponiveis, indisponiveis = buscar_disponiveis_poa(termo)
    
    col1, col2 = st.columns(2)
    col1.metric("Itens Disponíveis", len(disponiveis))
    col2.metric("Itens Indisponíveis/Ocultos", len(indisponiveis))

    st.subheader("✅ Resultados Disponíveis")
    if not disponiveis:
        st.warning("Nenhum item com estoque encontrado para este termo.")
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

    if st.checkbox("Mostrar Logs de Itens Indisponíveis"):
        for p in indisponiveis:
            st.text(f"Sem estoque: {p['productName']} - Status: {p['stock_status']}")
