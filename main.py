import streamlit as st
import requests
import unicodedata
import re

# Links dos logos e imagens
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Funções utilitárias
def remover_acentos(texto):
    if not texto: return ""
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
    texto_completo = f"{texto_nome} {texto_desc}"

    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        rolos = int(match.group(1))
        folhas_por_rolo = int(match.group(3))
        return rolos, folhas_por_rolo, rolos * folhas_por_rolo, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"

    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        total_folhas = int(match.group(1))
        return None, None, total_folhas, f"{total_folhas} {match.group(2)}"
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()
    
    if contem_papel_toalha(texto_completo):
        _, _, total_folhas, _ = extrair_info_papel_toalha(nome, descricao)
        if total_folhas: return f"R$ {preco_valor / total_folhas:.3f}/folha"

    # Lógica simplificada para KG, L, UN
    fontes = [descricao.lower(), nome.lower()]
    for fonte in fontes:
        m_g = re.search(r"(\d+[.,]?\d*)\s*(g|gramas?)", fonte)
        if m_g: return f"R$ {preco_valor / (float(m_g.group(1).replace(',', '.')) / 1000):.2f}/kg"
        m_ml = re.search(r"(\d+[.,]?\d*)\s*(ml|mililitros?)", fonte)
        if m_ml: return f"R$ {preco_valor / (float(m_ml.group(1).replace(',', '.')) / 1000):.2f}/L"
        m_un = re.search(r"(\d+[.,]?\d*)\s*(un|unidades?)", fonte)
        if m_un: return f"R$ {preco_valor / float(m_un.group(1).replace(',', '.')):.2f}/un"

    return "Sem unidade"

def extrair_valor_unitario(preco_unitario):
    match = re.search(r"R\$ (\d+[.,]?\d*)", preco_unitario)
    return float(match.group(1).replace(',', '.')) if match else float('inf')

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "searchProductsInput": {
                "clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 500, "search": [{"query": term}]
            }
        },
        "query": """query SearchProducts($searchProductsInput: SearchProductsInput!) {
            searchProducts(searchProductsInput: $searchProductsInput) {
                products { name price photosUrl sku stock description unit 
                promotion { isActive conditions { price } } } } }"""
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get("data", {}).get("searchProducts", {}).get("products", [])
    except: return []

# Layout Streamlit
st.set_page_config(page_title="Preços Nagumo", page_icon="🛒", layout="centered")
st.markdown("<style>header, footer {visibility: hidden;} .block-container {padding-top: 1rem;}</style>", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Nagumo</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Pesquisar no Nagumo:", "Banana").strip().lower()

if termo:
    with st.spinner("Buscando..."):
        termos_expandidos = gerar_formas_variantes(remover_acentos(termo))
        produtos_raw = []
        for t in termos_expandidos:
            produtos_raw.extend(buscar_nagumo(t))
        
        # Filtragem e Ordenação
        vistos = set()
        produtos_final = []
        palavras_busca = remover_acentos(termo).split()

        for p in produtos_raw:
            if p['sku'] in vistos: continue
            nome_desc = remover_acentos(f"{p['name']} {p.get('description','')}")
            if all(palavra in nome_desc for palavra in palavras_busca):
                vistos.add(p['sku'])
                
                # Preço e Promoção
                preco_final = p['price']
                promo = p.get("promotion") or {}
                if promo.get("isActive") and promo.get("conditions"):
                    preco_final = promo["conditions"][0]["price"]
                
                p['preco_exibir'] = preco_final
                p['unit_str'] = calcular_preco_unitario_nagumo(preco_final, p['description'] or "", p['name'])
                p['unit_val'] = extrair_valor_unitario(p['unit_str'])
                produtos_final.append(p)

        produtos_ordenados = sorted(produtos_final, key=lambda x: x['unit_val'])

        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="{LOGO_NAGUMO_URL}" width="120" style="border-radius: 8px; border: 1px solid #ddd; padding: 5px; background: white;">
                <p><small>{len(produtos_ordenados)} produtos encontrados</small></p>
            </div>
        """, unsafe_allow_html=True)

        for p in produtos_ordenados:
            img = p['photosUrl'][0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
            url = f"https://www.nagumo.com/p/{p['sku']}"
            
            preco_html = f"<b>R$ {p['preco_exibir']:.2f}</b>"
            if p['preco_exibir'] < p['price']:
                preco_html += f" <span style='color:red; font-size:0.8em;'>({int((1-p['preco_exibir']/p['price'])*100)}% OFF)</span>"

            st.markdown(f"""
                <div style="display: flex; gap: 15px; align-items: center; margin-bottom: 15px; padding: 10px; border-bottom: 1px solid #eee;">
                    <a href="{url}" target="_blank"><img src="{img}" width="80" style="border-radius: 5px;"></a>
                    <div style="flex: 1;">
                        <a href="{url}" target="_blank" style="text-decoration: none; color: #333;"><strong>{p['name']}</strong></a><br>
                        {preco_html}<br>
                        <small style="color: #666;">{p['unit_str']} | Estoque: {p['stock']}</small>
                    </div>
                </div>
            """, unsafe_allow_html=True)
