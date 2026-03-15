import streamlit as st
import requests
import json

# --- CONFIGURAÇÕES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

def buscar_todos_itens_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    
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
            return []

        data = response.json()
        products_edges = data.get('data', {}).get('search', {}).get('products', {}).get('edges', [])
        
        lista_itens = []

        for edge in products_edges:
            node = edge.get('node', {})
            sku = node.get('skus', [{}])[0]
            offer = sku.get('offers', {}).get('offers', [{}])[0]
            
            price = offer.get('price', 0)
            availability = offer.get('availability', "")
            
            # Adiciona todos os itens, independente de preço ou estoque
            lista_itens.append({
                "productId": node.get('id'),
                "productName": node.get('name'),
                "brand": node.get('brand', {}).get('name', 'N/A'),
                "price": price,
                "link": f"https://www.atacadao.com.br{node.get('slug')}/p",
                "img": node.get('image', [{}])[0].get('url', ''),
                "status": "Disponível" if "InStock" in availability else "Indisponível"
            })
        
        return lista_itens
    except Exception as e:
        st.error(f"Erro: {e}")
        return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Lista Completa", layout="wide")
st.title("🛒 Atacadão - Todos os Itens da API (Sem Filtro)")

termo = st.text_input("Pesquisar produto:", value="Arroz Camil")

if termo:
    itens = buscar_todos_itens_poa(termo)
    
    st.metric("Total de itens retornados", len(itens))

    for p in itens:
        with st.container():
            c1, c2, c3 = st.columns([1, 4, 1])
            if p['img']:
                c1.image(p['img'], width=80)
            
            # Estilização baseada no status
            cor_status = "green" if p['status'] == "Disponível" else "gray"
            
            c2.markdown(f"**{p['productName']}**")
            c2.markdown(f"<span style='color:{cor_status}; font-weight:bold;'>{p['status']}</span>", unsafe_allow_html=True)
            c2.write(f"Preço: R$ {p['price']:,.2f}")
            c2.caption(f"Marca: {p['brand']} | ID: {p['productId']}")
            
            c3.link_button("Ver no site", p['link'])
            st.divider()
