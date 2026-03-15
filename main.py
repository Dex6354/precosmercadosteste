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
            
            # Extraindo ofertas (lista de preços unitários e atacado)
            offers_data = node.get('offers', {}).get('offers', [])
            
            # Pegamos o primeiro preço da lista (geralmente o unitário)
            if offers_data:
                price = offers_data[0].get('price', 0)
                # Opcional: capturar preço de atacado se houver
                price_atacado = offers_data[1].get('price', 0) if len(offers_data) > 1 else None
            else:
                price = 0
                price_atacado = None

            lista_itens.append({
                "productId": node.get('id'),
                "productName": node.get('name'),
                "brand": node.get('brand', {}).get('name', 'N/A'),
                "price": price,
                "price_atacado": price_atacado,
                "link": f"https://www.atacadao.com.br{node.get('slug')}/p",
                "img": node.get('image', [{}])[0].get('url', '')
            })
        
        return lista_itens
    except Exception as e:
        st.error(f"Erro ao processar API: {e}")
        return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Consulta Completa", layout="wide")
st.title("🛒 Atacadão - Lista de Itens (Preços via Offers)")

termo = st.text_input("Pesquisar produto:", value="Arroz Camil")

if termo:
    itens = buscar_todos_itens_poa(termo)
    st.info(f"Foram encontrados {len(itens)} itens no JSON.")

    for p in itens:
        with st.container():
            c1, c2, c3 = st.columns([1, 4, 1])
            
            if p['img']:
                c1.image(p['img'], width=90)
            
            c2.markdown(f"### {p['productName']}")
            
            # Exibição de preços (Varejo e Atacado se existir)
            if p['price_atacado']:
                c2.markdown(f"**Varejo:** R$ {p['price']:,.2f} | **Atacado:** R$ {p['price_atacado']:,.2f}")
            else:
                c2.markdown(f"**Preço:** R$ {p['price']:,.2f}")
                
            c2.caption(f"Marca: {p['brand']} | ID: {p['productId']}")
            
            c3.write("") # Espaçador
            c3.link_button("Abrir Produto", p['link'])
            st.divider()
