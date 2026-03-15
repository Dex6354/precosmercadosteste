import streamlit as st
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES DE SESSÃO (CONFORME SOLICITADO) ---
# Unidade Poá: Seller 656
REGION_ID_POA = "v3.6358172645391" 
SALES_CHANNEL = "1"
SELLER_ID_POA = "atacadaobr656"

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
    
    # Inclusão dos parâmetros de validação de canal de venda e região
    params = {
        "ft": termo,
        "_from": 0,
        "_to": qtd_itens - 1,
        "sc": SALES_CHANNEL,
        "regionId": REGION_ID_POA
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Cookie": f"vtex_segment=sn={SALES_CHANNEL}&regionId={REGION_ID_POA};" # Simula a sessão validada
    }
    
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        if r.status_code in [200, 206]:
            return r.json()
    except:
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Poá - Validação de Estoque", layout="wide")

st.title("🛒 Atacadão - Pesquisa com Validação de Sessão")
st.caption(f"Loja: {SELLER_ID_POA} | Region: {REGION_ID_POA} | Canal: {SALES_CHANNEL}")

termo_busca = st.text_input("Pesquisar:", value="Arroz Camil")

if termo_busca:
    json_data = buscar_atacadao(termo_busca)
    
    if not json_data:
        st.error("Nenhum dado retornado pela API.")
    else:
        # FILTRAGEM RIGOROSA (O QUE O SITE FAZ)
        produtos_disponiveis = []
        for p in json_data:
            possui_estoque = False
            try:
                # O site valida se o seller específico (656) tem o item disponível
                for item in p.get('items', []):
                    for seller in item.get('sellers', []):
                        # Valida se o vendedor é o de Poá ou se é o vendedor principal (1) com estoque
                        if seller.get('sellerId') in [SELLER_ID_POA, "1"]:
                            offer = seller.get('commertialOffer', {})
                            if offer.get('AvailableQuantity', 0) > 0 and offer.get('Price', 0) > 0:
                                possui_estoque = True
                                break
                    if possui_estoque: break
                
                if possui_estoque:
                    produtos_disponiveis.append(p)
            except:
                continue

        st.success(f"Encontrados {len(produtos_disponiveis)} produtos disponíveis no site para Poá.")
        
        # Listagem
        for idx, p in enumerate(json_data):
            # Determinamos se o item deve ser exibido ou apenas depurado
            item_obj = p.get('items', [{}])[0]
            seller_main = item_obj.get('sellers', [{}])[0]
            offer = seller_main.get('commertialOffer', {})
            
            disponivel = (offer.get('AvailableQuantity', 0) > 0 and offer.get('Price', 0) > 0)
            
            with st.container():
                col1, col2 = st.columns([1, 4])
                with col1:
                    img = item_obj.get('images', [{}])[0].get('imageUrl', '')
                    if img: st.image(img, width=70)
                
                with col2:
                    status_text = "✅ DISPONÍVEL" if disponivel else "❌ INDISPONÍVEL (OCULTO NO SITE)"
                    st.markdown(f"**{p.get('productName')}**")
                    st.markdown(f"<small>{status_text}</small>", unsafe_allow_html=True)
                    
                    if disponivel:
                        preco = offer.get('Price', 0)
                        _, label_un = calcular_preco_unidade(p.get('productName'), preco)
                        st.markdown(f"<span style='color:red; font-weight:bold;'>R$ {preco:,.2f}</span> <small>{label_un if label_un else ''}</small>", unsafe_allow_html=True)

                    # DEBUGGER POR ITEM
                    with st.expander("Debug JSON"):
                        st.json({
                            "ProductName": p.get('productName'),
                            "AvailableQuantity": offer.get('AvailableQuantity'),
                            "IsAvailable": offer.get('IsAvailable'),
                            "Price": offer.get('Price'),
                            "SellerId": seller_main.get('sellerId'),
                            "RegionId_Request": REGION_ID_POA
                        })
            st.divider()
