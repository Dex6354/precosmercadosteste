import streamlit as st
import requests

# IDs de Região identificados (Exemplos baseados no comportamento VTEX)
# Nota: Estes IDs podem variar, use o debugger para confirmar o seu
LOJAS = {
    "Poá - SP": "v3.6358172645391", # Exemplo de ID de Região para Poá
    "Suzano - SP": "v3.7849123456789" # Exemplo de ID de Região para Suzano
}

def buscar_com_loja_especifica(termo, region_id):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    params = {
        "ft": termo,
        "sc": "1",
        # O segredo para mudar de Poá para Suzano sem cookies complexos
        "regionId": region_id 
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    
    r = requests.get(url, params=params, headers=headers)
    return r.json() if r.status_code == 200 else [], r.url

st.title("Comparador de Estoque Regional")

loja_selecionada = st.selectbox("Selecione a Loja:", list(LOJAS.keys()))
termo_busca = st.text_input("Produto:", "Arroz")

if termo_busca:
    region_id = LOJAS[loja_selecionada]
    produtos, debug_url = buscar_com_loja_especifica(termo_busca, region_id)
    
    st.caption(f"DEBUG: Consultando região `{region_id}` via `{debug_url}`")
    
    for p in produtos:
        item = p['items'][0]
        seller = item['sellers'][0]['commertialOffer']
        estoque = seller.get('AvailableQuantity', 0)
        
        col1, col2 = st.columns([4, 1])
        col1.write(f"**{p['productName']}**")
        if estoque > 0:
            col2.success(f"Estoque: {estoque}")
        else:
            col2.error("Sem estoque")
