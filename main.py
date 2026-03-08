import streamlit as st
import requests
import unicodedata
import re

# Links dos logos e imagens
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Funções utilitárias
def remover_acentos(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    variantes = {termo}
    if termo.endswith("s"):
        variantes.add(termo[:-1])
    else:
        variantes.add(termo + "s")
    return list(variantes)

def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_nome = remover_acentos(nome.lower())
    texto_desc = remover_acentos(descricao.lower())
    
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        rolos = int(match.group(1)); folhas = int(match.group(3))
        return rolos, folhas, rolos * folhas, f"{rolos} {match.group(2)}, {folhas} {match.group(4)}"

    texto_completo = f"{texto_nome} {texto_desc}"
    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        total = int(match.group(1))
        return None, None, total, f"{total} {match.group(2)}"
    
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()

    if contem_papel_toalha(texto_completo):
        _, _, total_folhas, _ = extrair_info_papel_toalha(nome, descricao)
        if total_folhas and total_folhas > 0:
            return f"R$ {preco_valor / total_folhas:.3f}/folha"
        return "Preço por folha: n/d"

    if "papel higi" in texto_completo:
        match_rolos = re.search(r"(?:leve|lv|c/|unidades?|rolos?)\s*0*(\d+)", texto_completo)
        match_metros = re.search(r"(\d+[.,]?\d*)\s*(m|metros?|mt)", texto_completo)
        if match_rolos and match_metros:
            try:
                rolos = int(match_rolos.group(1))
                metros = float(match_metros.group(1).replace(',', '.'))
                if rolos > 0 and metros > 0:
                    return f"R$ {preco_valor / rolos / metros:.3f}/m"
            except: pass

    fontes = [descricao.lower(), nome.lower()]
    for fonte in fontes:
        match_g = re.search(r"(\d+[.,]?\d*)\s*(g|gramas?)", fonte)
        if match_g: return f"R$ {preco_valor / (float(match_g.group(1).replace(',', '.')) / 1000):.2f}/kg"
        match_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo)", fonte)
        if match_kg: return f"R$ {preco_valor / float(match_kg.group(1).replace(',', '.')):.2f}/kg"
        match_ml = re.search(r"(\d+[.,]?\d*)\s*(ml|mililitros?)", fonte)
        if match_ml: return f"R$ {preco_valor / (float(match_ml.group(1).replace(',', '.')) / 1000):.2f}/L"
        match_l = re.search(r"(\d+[.,]?\d*)\s*(l|litros?)", fonte)
        if match_l: return f"R$ {preco_valor / float(match_l.group(1).replace(',', '.')):.2f}/L"

    return "Sem unidade"

def extrair_valor_unitario(preco_unitario):
    match = re.search(r"R\$ (\d+[.,]?\d*)", preco_unitario)
    return float(match.group(1).replace(',', '.')) if match else float('inf')

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.nagumo.com",
        "User-Agent": "Mozilla/5.0",
        "apollographql-client-name": "Ecommerce SSR"
    }
    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "searchProductsInput": {
                "clientId": "NAGUMO", "storeReference": "22", "currentPage": 1,
                "pageSize": 500, "search": [{"query": term}], "filters": {}
            }
        },
        "query": """
        query SearchProducts($searchProductsInput: SearchProductsInput!) {
          searchProducts(searchProductsInput: $searchProductsInput) {
            products { name price photosUrl sku description unit
              promotion { isActive conditions { price } }
            }
          }
        } """
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json().get("data", {}).get("searchProducts", {}).get("products", [])
    except: return []

# Configuração da página Streamlit
st.set_page_config(page_title="Preços Nagumo", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        header { visibility: hidden; }
        .product-container { display: flex; align-items: center; gap: 10px; padding: 10px 0; border-bottom: 1px solid #eee; }
        .product-image { min-width: 80px; max-width: 80px; }
        .product-info { flex: 1; font-size: 0.85rem; }
        .price-tag { color: #1e88e5; font-weight: bold; }
        .unit-tag { color: gray; font-size: 0.75rem; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛒 Preços Nagumo</h3>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip().lower()

if termo:
    termos_expandidos = gerar_formas_variantes(remover_acentos(termo))
    palavras_termo = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando no Nagumo..."):
        produtos_raw = []
        for t in termos_expandidos:
            produtos_raw.extend(buscar_nagumo(t))
        
        # Filtro e Processamento
        vistos = set()
        produtos_processados = []
        for p in produtos_raw:
            if p['sku'] in vistos: continue
            vistos.add(p['sku'])
            
            nome_desc = remover_acentos(f"{p['name']} {p.get('description', '')}")
            if all(palavra in nome_desc for palavra in palavras_termo):
                # Lógica de preço
                promo = p.get("promotion") or {}
                cond = promo.get("conditions") or []
                preco_atual = cond[0].get("price") if promo.get("isActive") and cond else p.get("price", 0)
                
                # Unidade e Título
                p['preco_unit_str'] = calcular_preco_unitario_nagumo(preco_atual, p.get('description',''), p['name'])
                p['preco_unit_val'] = extrair_valor_unitario(p['preco_unit_str'])
                p['url_final'] = f"https://www.nagumo.com/p/{p['sku']}"
                
                produtos_processados.append(p)

        # Ordenação pelo melhor preço unitário
        produtos_ordenados = sorted(produtos_processados, key=lambda x: x['preco_unit_val'])

        # Exibição (Container Único)
        st.markdown(f'<img src="{LOGO_NAGUMO_URL}" width="120">', unsafe_allow_html=True)
        st.write(f"Encontrados {len(produtos_ordenados)} produtos.")

        for p in produtos_ordenados:
            img = p['photosUrl'][0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
            promo = p.get("promotion") or {}
            cond = promo.get("conditions") or []
            preco_final = cond[0].get("price") if promo.get("isActive") and cond else p.get("price", 0)

            st.markdown(f"""
                <div class="product-container">
                    <img src="{img}" class="product-image">
                    <div class="product-info">
                        <a href="{p['url_final']}" target="_blank" style="text-decoration: none; color: black;">
                            <strong>{p['name']}</strong>
                        </a><br>
                        <span class="price-tag">R$ {preco_final:.2f}</span><br>
                        <span class="unit-tag">{p['preco_unit_str']}</span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
