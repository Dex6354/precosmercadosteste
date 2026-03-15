import streamlit as st
import requests
import unicodedata
import re
import json

# --- CONFIGURAÇÕES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"

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

def buscar_atacadao_graphql(termo, qtd_itens=20):
    url = "https://www.atacadao.com.br/api/graphql"
    
    # Payload baseado nos parâmetros fornecidos
    variables = {
        "first": qtd_itens,
        "after": "0",
        "sort": "score_desc",
        "term": termo,
        "selectedFacets": [
            {"key": "region-id", "value": "U1cjYXRhY2FkYW9icjY1Ng=="},
            {"key": "channel", "value": "{\"salesChannel\":\"1\",\"seller\":\"atacadaobr656\",\"regionId\":\"U1cjYXRhY2FkYW9icjY1Ng==\"}"},
            {"key": "locale", "value": "pt-BR"}
        ]
    }
    
    # Query simplificada para buscar os dados básicos necessários para a interface
    query = """
    query ProductsQuery($first: Int!, $after: String!, $sort: String!, $term: String!, $selectedFacets: [SelectedFacetInput!]) {
      search(first: $first, after: $after, sort: $sort, term: $term, selectedFacets: $selectedFacets) {
        products {
          nodes {
            id
            name
            brand
            link
            reference
            items {
              images {
                url
              }
              sellers {
                commertialOffer {
                  Price
                }
              }
            }
          }
        }
      }
    }
    """
    
    payload = {
        "operationName": "ProductsQuery",
        "variables": variables,
        "query": query
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('data', {}).get('search', {}).get('products', {}).get('nodes', [])
    except Exception as e:
        st.error(f"Erro na requisição: {e}")
        return []
    return []

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Full Search", layout="wide")

st.markdown("""
    <style>
        .product-card {
            border-bottom: 1px solid #eee; padding: 15px;
            display: flex; align-items: center; background: white;
        }
        .index-box { font-family: monospace; color: #888; margin-right: 15px; font-size: 1.1rem; }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .details { font-size: 0.8rem; color: #666; font-family: monospace; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão - GraphQL Search")

termo_busca = st.text_input("Pesquisar:", value="Arroz Camil")

if termo_busca:
    produtos = buscar_atacadao_graphql(termo_busca)
    
    if not produtos:
        st.warning("Nenhum produto encontrado ou erro na API.")
    else:
        st.success(f"Encontrados {len(produtos)} produtos.")
        
        for idx, p in enumerate(produtos):
            try:
                p_id = p.get('id')
                p_name = p.get('name')
                brand = p.get('brand')
                link = "https://www.atacadao.com.br" + p.get('link', '')
                ref = p.get('reference')
                
                # Acesso aos itens e preços no formato GraphQL
                item_obj = p['items'][0]
                img = item_obj.get('images', [{}])[0].get('url', '')
                preco = item_obj.get('sellers', [{}])[0].get('commertialOffer', {}).get('Price', 0)
                
                _, label_un = calcular_preco_unidade(p_name, preco)

                st.markdown(f"""
                    <div class="product-card">
                        <div class="index-box">{idx}:{{</div>
                        <img src="{img}" width="60" style="margin-right:20px">
                        <div style="flex: 1;">
                            <div style="font-weight: bold;">{p_name}</div>
                            <div class="details">
                                "id": "{p_id}"<br>
                                "brand": "{brand}"<br>
                                "reference": "{ref}"
                            </div>
                            <div class="price">R$ {preco:,.2f} {f'<span style="font-size:0.8rem; color:gray;">({label_un})</span>' if label_un else ''}</div>
                        </div>
                        <div class="index-box">}}</div>
                        <a href="{link}" target="_blank">
                            <button style="cursor:pointer; background:#d32f2f; color:white; border:none; padding:5px 10px; border-radius:4px;">Ver</button>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.write(f"Erro ao processar item {idx}: {e}")
                continue
