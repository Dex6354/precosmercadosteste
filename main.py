import streamlit as st
import requests
import re

# --- CONFIGURAÇÕES ---
# O sc=1 é o padrão, a mágica acontece no cookie e na simulação de estoque
SC_PADRAO = "1"

def buscar_atacadao_poa(termo, qtd_itens=50):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": SC_PADRAO
    }
    
    # Headers extraídos do seu HAR para garantir a regionalização
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://www.atacadao.com.br",
        "Referer": f"https://www.atacadao.com.br/s?q={termo}",
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code in [200, 206]:
            dados = r.json()
            produtos_com_estoque = []
            
            for p in dados:
                item = p['items'][0]
                oferta = item['sellers'][0]['commertialOffer']
                
                # O Atacadão usa AvailableQuantity para indicar estoque na loja selecionada
                estoque = oferta.get('AvailableQuantity', 0)
                preco = oferta.get('Price', 0)
                
                # Se estoque > 0, o item está disponível em POA
                if estoque > 0:
                    produtos_com_estoque.append({
                        "id": p.get('productId'),
                        "nome": p.get('productName'),
                        "preco": preco,
                        "estoque": estoque,
                        "link": p.get('link'),
                        "img": item.get('images', [{}])[0].get('imageUrl', '')
                    })
            return produtos_com_estoque, r.url
    except Exception as e:
        return [], str(e)
    return [], "Erro na requisição"

# --- INTERFACE ---
st.title("🛒 Atacadão POA - Verificador de Estoque")

termo = st.text_input("Produto para POA:", value="Arroz Camil")

if termo:
    produtos, debug_url = buscar_atacadao_poa(termo)
    
    with st.expander("🔍 Debugger de Loja"):
        st.write(f"**URL da API:** `{debug_url}`")
        st.write(f"**Itens Disponíveis em POA:** {len(produtos)}")

    if not produtos:
        st.error("Nenhum item com estoque disponível encontrado para POA.")
    else:
        for p in produtos:
            col1, col2 = st.columns([1, 4])
            with col1:
                st.image(p['img'], width=100)
            with col2:
                st.markdown(f"### {p['nome']}")
                st.markdown(f"**Preço: R$ {p['preco']:,.2f}**")
                st.info(f"📦 Estoque disponível: {p['estoque']} unidades")
                st.link_button("Ver no Site", p['link'])
            st.divider()
