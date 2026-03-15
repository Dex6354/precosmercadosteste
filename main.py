import streamlit as st
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
REGION_ID_POA = "v3.6358172645391"

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?|l|litros?|ml)', desc_minus)
    if m_kg:
        try:
            valor = float(m_kg.group(1).replace(',', '.'))
            unidade = m_kg.group(2)
            if unidade in ['g', 'grama', 'gramas', 'ml']:
                valor /= 1000
            if valor > 0:
                preco_un = preco_total / valor
                sufixo = "/kg" if unidade[0] in ['k', 'g'] else "/L"
                return preco_un, f"R$ {preco_un:.2f}{sufixo}"
        except: pass
    return None, None

def buscar_atacadao(termo, qtd_itens=50):
    url = "https://www.atacadao.com.br/api/catalog_system/pub/products/search"
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": 1,
        "regionId": REGION_ID_POA
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code in [200, 206]:
            return r.json()
    except:
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Debugger", layout="wide")

st.title("🛒 Atacadão - Debugger de Estoque (Poá)")

termo_busca = st.text_input("Pesquisar:", value="Arroz Camil")

if termo_busca:
    json_data = buscar_atacadao(termo_busca)
    
    if not json_data:
        st.error("Nenhum dado retornado.")
    else:
        st.info(f"API retornou {len(json_data)} itens no total. Analise o status de cada um abaixo:")

        for idx, p in enumerate(json_data):
            try:
                # Extração de dados para o Debugger
                item_obj = p.get('items', [{}])[0]
                seller_obj = item_obj.get('sellers', [{}])[0]
                offer = seller_obj.get('commertialOffer', {})
                
                # Campos de controle de estoque
                available_qty = offer.get('AvailableQuantity', 0)
                is_available = offer.get('IsAvailable', False)
                price = offer.get('Price', 0)
                
                # Lógica de filtro do site (suposição para teste)
                tem_estoque_real = (available_qty > 0) and (price > 0)

                # Container visual
                with st.container():
                    col1, col2 = st.columns([1, 4])
                    
                    with col1:
                        img = item_obj.get('images', [{}])[0].get('imageUrl', '')
                        if img: st.image(img, width=80)
                    
                    with col2:
                        cor_status = "green" if tem_estoque_real else "red"
                        st.markdown(f"**{p.get('productName')}**")
                        st.markdown(f"<span style='color:{cor_status}'>● {'DISPONÍVEL NO SITE' if tem_estoque_real else 'OCULTO NO SITE'}</span>", unsafe_allow_html=True)
                        
                        # Painel de Debug
                        with st.expander(f"Ver Dados Técnicos (Item {idx})"):
                            st.json({
                                "productId": p.get('productId'),
                                "AvailableQuantity": available_qty,
                                "IsAvailable": is_available,
                                "Price": price,
                                "SellerId": seller_obj.get('sellerId'),
                                "listPrice": offer.get('ListPrice')
                            })
                st.divider()
                
            except Exception as e:
                st.error(f"Erro ao processar item {idx}: {e}")
