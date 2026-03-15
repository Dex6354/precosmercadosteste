import streamlit as st
import requests
import unicodedata
import re
import json

# --- CONFIGURAÇÕES ---
URL_GRAPHQL = "https://www.atacadao.com.br/api/graphql"
# ID de região em Base64 conforme seu link: U1cjYXRhY2FkYW9icjY1Ng==
REGION_ID_B64 = "U1cjYXRhY2FkYW9icjY1Ng==" 

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

def buscar_atacadao_graphql(termo):
    # Variáveis conforme seu link correto
    variables = {
        "first": 20,
        "after": "0",
        "sort": "score_desc",
        "term": termo,
        "selectedFacets": [
            {"key": "region-id", "value": REGION_ID_B64},
            {"key": "channel", "value": json.dumps({"salesChannel": "1", "seller": "atacadaobr656", "regionId": REGION_ID_B64})},
            {"key": "locale", "value": "pt-BR"}
        ]
    }
    
    # Payload simplificado da ProductsQuery
    payload = {
        "operationName": "ProductsQuery",
        "variables": variables,
        # Nota: Em uma implementação real, o campo 'query' contendo o schema GraphQL seria necessário
        # mas muitas APIs da VTEX aceitam apenas o operationName se a query já estiver persistida.
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        # Usando GET conforme o link fornecido para facilitar a consulta
        r = requests.get(URL_GRAPHQL, params={"operationName": "ProductsQuery", "variables": json.dumps(variables)}, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # A estrutura do GraphQL costuma ser data -> search -> products
            return data.get('data', {}).get('search', {}).get('products', [])
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Poá - GraphQL", layout="wide")

st.title("🛒 Atacadão Poá - Busca Real (GraphQL)")

termo_busca = st.text_input("Pesquisar:", value="Arroz Camil")

if termo_busca:
    produtos = buscar_atacadao_graphql(termo_busca)
    
    if not produtos:
        st.warning("Nenhum produto encontrado ou erro na estrutura da API. Verifique o console/debug.")
        # Debug para verificar o que a API está retornando
        if st.checkbox("Ver resposta bruta da API"):
            st.write(produtos)
    else:
        st.success(f"Encontrados {len(produtos)} produtos ativos em Poá.")
        
        for idx, p in enumerate(produtos):
            try:
                # Estrutura GraphQL: p['itemMetas'] ou p['nodes'] dependendo do schema
                # Abaixo ajustado para o padrão comum de retorno
                name = p.get('name', p.get('productName', 'Sem nome'))
                brand = p.get('brand', 'Sem marca')
                
                # Acessando o preço na primeira SKU disponível
                sku = p.get('items', [{}])[0]
                img = sku.get('images', [{}])[0].get('imageUrl', '')
                offer = sku.get('sellers', [{}])[0].get('commertialOffer', {})
                preco = offer.get('Price', 0)
                
                _, label_un = calcular_preco_unidade(name, preco)

                st.markdown(f"""
                    <div style="border-bottom: 1px solid #eee; padding: 15px; display: flex; align-items: center;">
                        <div style="color: #888; margin-right: 15px;">{idx}</div>
                        <img src="{img}" width="60" style="margin-right:20px">
                        <div style="flex: 1;">
                            <div style="font-weight: bold;">{name}</div>
                            <div style="font-size: 0.8rem; color: #666;">Marca: {brand}</div>
                            <div style="color: #d32f2f; font-weight: bold; font-size: 1.2rem;">
                                R$ {preco:,.2f} {f'<span style="font-size:0.8rem; color:gray;">({label_un})</span>' if label_un else ''}
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            except:
                continue

if st.sidebar.button("Gerar Link de Consulta Manual"):
    # Gera o link URL Encoded para você testar no navegador
    import urllib.parse
    vars_json = json.dumps({"first":20,"after":"0","sort":"score_desc","term":termo_busca,"selectedFacets":[{"key":"region-id","value":REGION_ID_B64},{"key":"channel","value":json.dumps({"salesChannel":"1","seller":"atacadaobr656","regionId":REGION_ID_B64})},{"key":"locale","value":"pt-BR"}]})
    link_final = f"{URL_GRAPHQL}?operationName=ProductsQuery&variables={urllib.parse.quote(vars_json)}"
    st.sidebar.code(link_final)
