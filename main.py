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
    
    items_per_page = 20
    current_after = 0
    total_encontrado = 0
    primeira_busca = True

    while primeira_busca or current_after < total_encontrado:
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
            },
            # Query explícita para garantir que o totalCount e os nós venham corretamente
            "query": "query ProductsQuery($first: Int, $after: String, $sort: String, $term: String, $selectedFacets: [SelectedFacetInput]) { search(first: $first, after: $after, sort: $sort, term: $term, selectedFacets: $selectedFacets) { products { pageInfo { totalCount } edges { node { id name slug brand { name } image { url } skus { offers { offers { price availability } } } } } } } }"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            search_result = data.get('data', {}).get('search', {}).get('products', {})
            
            if primeira_busca:
                total_encontrado = search_result.get('pageInfo', {}).get('totalCount', 0)
                primeira_busca = False
                if total_encontrado == 0:
                    break

            edges = search_result.get('edges', [])
            if not edges:
                break

            for edge in edges:
                node = edge.get('node', {})
                skus = node.get('skus', [])
                if not skus: continue
                
                # Extração segura de preço e estoque
                offers_list = skus[0].get('offers', {}).get('offers', [])
                if not offers_list: continue
                
                offer = offers_list[0]
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

            current_after += items_per_page

        except Exception as e:
            st.error(f"Erro: {e}")
            break
            
    return itens_disponiveis, itens_indisponiveis

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Poá - Full", layout="wide")
st.title("🛒 Busca Atacadão (Todas as Páginas)")

termo = st.text_input("Produto:", value="Banana")

if termo:
    with st.spinner(f"Vasculhando o catálogo para '{termo}'..."):
        disp, indisp = buscar_todos_produtos_poa(termo)
    
    c1, c2 = st.columns(2)
    c1.metric("Disponíveis", len(disp))
    c2.metric("Total no Catálogo", len(disp) + len(indisp))

    if not disp:
        st.warning("Nada disponível com estoque no momento.")
    else:
        for p in disp:
            with st.container():
                col_img, col_txt, col_btn = st.columns([1, 4, 1])
                if p['img']: col_img.image(p['img'], width=80)
                col_txt.markdown(f"**{p['productName']}**")
                col_txt.markdown(f"**R$ {p['price']:,.2f}**")
                col_btn.link_button("Ver site", p['link'])
                st.divider()

    if st.checkbox("Ver log de indisponíveis"):
        st.write(indisp)
