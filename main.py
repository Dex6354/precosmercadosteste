import streamlit as st
import requests
import json

# --- CONFIGURAÇÕES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

def buscar_todos_itens_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    lista_itens = []
    after = 0
    first = 50  # Buscando 50 por vez para ser mais rápido
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    while True:
        payload = {
            "operationName": "ProductsQuery",
            "variables": {
                "first": first,
                "after": str(after),
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
            products = data.get('data', {}).get('search', {}).get('products', {}).get('edges', [])
            
            if not products:
                break  # Para se não houver mais produtos
            
            for edge in products:
                node = edge.get('node', {})
                offers = node.get('offers', {}).get('offers', [])
                
                price = 0.0
                price_atacado = None
                
                if offers:
                    # Tenta pegar preço de varejo e atacado
                    price = offers[0].get('price', 0.0)
                    if len(offers) > 1:
                        price_atacado = offers[1].get('price')

                lista_itens.append({
                    "productName": node.get('name', 'N/A'),
                    "brand": node.get('brand', {}).get('name', 'N/A'),
                    "price": price,
                    "price_atacado": price_atacado,
                    "link": f"https://www.atacadao.com.br{node.get('slug')}/p",
                    "img": node.get('image', [{}])[0].get('url', '')
                })

            # Verifica se ainda há mais páginas baseado no total de itens (opcional) ou se a lista cresceu
            total_count = data.get('data', {}).get('search', {}).get('products', {}).get('pageInfo', {}).get('totalCount', 0)
            
            after += first
            if after >= total_count:
                break
                
        except Exception as e:
            st.error(f"Erro ao processar API: {e}")
            break
            
    return lista_itens

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão - Consulta Completa", layout="wide")
st.title("🛒 Atacadão - Todos os Itens")

termo = st.text_input("Pesquisar produto:", value="Banana")

if termo:
    with st.spinner(f"Buscando todos os resultados para '{termo}'..."):
        itens = buscar_todos_itens_poa(termo)
    
    st.success(f"Foram encontrados {len(itens)} itens no total.")

    for p in itens:
        with st.container():
            c1, c2, c3 = st.columns([1, 4, 1])
            
            if p['img']:
                c1.image(p['img'], width=90)
            
            c2.markdown(f"### {p['productName']}")
            
            # Exibição de preços
            texto_preco = f"**Varejo:** R$ {p['price']:,.2f}"
            if p['price_atacado']:
                texto_preco += f" | **Atacado:** R$ {p['price_atacado']:,.2f}"
            
            c2.markdown(texto_preco)
            c3.markdown(f"[Ver no site]({p['link']})")
            st.divider()
