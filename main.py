import streamlit as st
import requests
import json

# --- CONFIGURAÇÕES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"

def buscar_disponiveis_poa(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }
    
    itens_disponiveis = []
    itens_indisponiveis = []
    
    # Controle de paginação
    items_per_page = 50  # Otimizado para 50 itens por vez
    cursor = "0"
    has_next_page = True

    try:
        while has_next_page:
            payload = {
                "operationName": "ProductsQuery",
                "variables": {
                    "first": items_per_page,
                    "after": cursor,
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
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()
            
            search_data = data.get("data", {}).get("search", {})
            products = search_data.get("products", [])
            
            if not products:
                break

            for prod in products:
                # Lógica de extração de dados
                price = prod.get('offers', {}).get('lowPrice', 0)
                available = prod.get('offers', {}).get('offers', [{}])[0].get('availability', '')
                
                info_item = {
                    "productName": prod.get('productName'),
                    "price": price,
                    "img": prod.get('items', [{}])[0].get('images', [{}])[0].get('imageUrl', ''),
                    "link": prod.get('link')
                }

                if "InStock" in available or price > 0:
                    itens_disponiveis.append(info_item)
                else:
                    itens_indisponiveis.append(info_item)

            # Verifica se há mais páginas
            page_info = search_data.get("pageInfo", {})
            total_count = search_data.get("recordsFiltered", 0)
            
            # Atualiza o cursor para a próxima página
            cursor = str(len(itens_disponiveis) + len(itens_indisponiveis))
            
            # Condição de parada: se já pegamos tudo ou se a API diz que não tem mais
            if int(cursor) >= total_count or not products:
                has_next_page = False

        return itens_disponiveis, itens_indisponiveis

    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return [], []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Atacadão Poá - Full Search", layout="wide")
st.title("🛒 Atacadão - Todos os Resultados (Poá)")

termo = st.text_input("Pesquisar produto:", value="Banana")

if termo:
    with st.spinner(f"Buscando todos os itens para '{termo}'..."):
        disponiveis, indisponiveis = buscar_disponiveis_poa(termo)
    
    col1, col2 = st.columns(2)
    col1.metric("Itens Disponíveis", len(disponiveis))
    col2.metric("Itens Indisponíveis/Ocultos", len(indisponiveis))

    st.subheader(f"✅ Resultados Encontrados: {len(disponiveis)}")
    if not disponiveis:
        st.warning("Nenhum item com estoque encontrado.")
    else:
        # Exibição em Grid para facilitar a visualização de muitos itens
        cols = st.columns(4)
        for idx, p in enumerate(disponiveis):
            with cols[idx % 4]:
                st.image(p['img'], width=120) if p['img'] else st.write("Sem imagem")
                st.caption(p['productName'])
                st.markdown(f"**R$ {p['price']:,.2f}**")
                st.divider()
