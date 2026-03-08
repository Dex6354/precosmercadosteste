import streamlit as st
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações para Shibata
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

# Links dos logos
LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
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
    
def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    if match_leve:
        q_rolos = int(match_leve.group(1))
    else:
        match_rolos = re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)
        q_rolos = int(match_rolos.group(1)) if match_rolos else None
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    match_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if match_kg:
        peso = float(match_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if match_g:
        peso = float(match_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = None
    match_unidades = re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)
    if match_unidades:
        qtd_unidades = int(match_unidades.group(1))

    folhas_por_unidade = None
    match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)\s*cada', desc)
    if not match_folhas:
        match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)', desc)
    if match_folhas:
        folhas_por_unidade = int(match_folhas.group(1))

    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        preco_por_folha = preco_total / folhas_leve if folhas_leve else None
        return folhas_leve, preco_por_folha

    match_leve_pague = re.findall(r'(\d+)', desc)
    folhas_leve = None
    if 'leve' in desc and 'folhas' in desc and match_leve_pague:
        folhas_leve = max(int(n) for n in match_leve_pague)

    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return total_folhas, preco_total / total_folhas
    return None, None

def formatar_preco_unidade_personalizado(preco_total, quantidade, unidade):
    if not unidade:
        return f"R$ {preco_total:.2f}".replace('.', ',')
    unidade = unidade.lower()
    if quantidade and quantidade != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(quantidade).replace('.', ',')}{unidade}"
    else:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{unidade}"

# Funções Shibata
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        response = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {})
            if data:
                return [p for p in data.get('produtos', []) if p.get("disponivel", True)]
            return []
        return []
    except:
        return []

# Funções Nagumo
def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_nome = remover_acentos(nome.lower())
    texto_desc = remover_acentos(descricao.lower())
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        total = int(match.group(1)) * int(match.group(3))
        return int(match.group(1)), int(match.group(3)), total, f"{match.group(1)} un, {match.group(3)} folhas"
    
    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        return None, None, int(match.group(1)), f"{match.group(1)} folhas"
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()
    if contem_papel_toalha(texto_completo):
        _, _, total_folhas, _ = extrair_info_papel_toalha(nome, descricao)
        if total_folhas:
            return f"R$ {preco_valor / total_folhas:.3f}/folha"
    
    fontes = [descricao.lower(), nome.lower()]
    for fonte in fontes:
        m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo)", fonte)
        if m_kg: return f"R$ {preco_valor / float(m_kg.group(1).replace(',', '.')):.2f}/kg"
        m_g = re.search(r"(\d+[.,]?\d*)\s*(g|gramas?)", fonte)
        if m_g: return f"R$ {preco_valor / (float(m_g.group(1).replace(',', '.')) / 1000):.2f}/kg"
    
    return f"R$ {preco_valor:.2f}/{unidade_api if unidade_api else 'un'}"

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
                "clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50,
                "search": [{"query": term}], "filters": {}
            }
        },
        "query": """
        query SearchProducts($searchProductsInput: SearchProductsInput!) {
          searchProducts(searchProductsInput: $searchProductsInput) {
            products { name price photosUrl sku stock description unit 
              promotion { isActive type conditions { price } }
            }
          }
        }"""
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        res_json = response.json()
        # Verificação segura de camadas aninhadas
        data = res_json.get("data")
        if data:
            search_results = data.get("searchProducts")
            if search_results:
                return search_results.get("products") or []
        return []
    except:
        return []

# Interface Streamlit
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")
st.markdown("""<style>
    .block-container { padding-top: 1rem; }
    div, span, strong, small { font-size: 0.75rem !important; }
    [data-testid="stColumn"] { overflow-y: auto; max-height: 80vh; border: 1px solid #eee; padding: 10px; border-radius: 8px; }
    header {display: none !important;}
</style>""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_expandidos = gerar_formas_variantes(remover_acentos(termo))
    palavras_termo = remover_acentos(termo).split()

    with st.spinner("Buscando..."):
        # SHIBATA (Inalterado conforme pedido)
        produtos_shibata = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(buscar_pagina_shibata, t, p) for t in termos_expandidos for p in range(1, 6)]
            for f in as_completed(futures): produtos_shibata.extend(f.result())
        
        vistos = set()
        shibata_final = []
        for p in produtos_shibata:
            if p.get('id') not in vistos:
                vistos.add(p.get('id'))
                desc = p.get('descricao', '').lower()
                if all(pal in remover_acentos(desc) for pal in palavras_termo):
                    p_id = p.get('produto_id')
                    p['url_shibata'] = f"https://www.loja.shibata.com.br/produto/{p_id}/{slugify(desc)}" if p_id else "#"
                    preco = float(p.get('oferta', {}).get('preco_oferta') or p.get('preco') or 0)
                    p['preco_unit_str'] = formatar_preco_unidade_personalizado(preco, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['sort_val'], _ = calcular_preco_unidade(desc, preco)
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x.get('sort_val') or 999)

        # NAGUMO (Corrigido)
        nagumo_raw = []
        for t in termos_expandidos: nagumo_raw.extend(buscar_nagumo(t))
        
        nagumo_final = []
        vistos_sku = set()
        for p in nagumo_raw:
            sku = p.get('sku')
            if sku and sku not in vistos_sku:
                vistos_sku.add(sku)
                nome = p.get('name', '')
                desc = p.get('description', '')
                if all(pal in remover_acentos(f"{nome} {desc}") for pal in palavras_termo):
                    p['url_nagumo'] = f"https://www.nagumo.com/p/{sku}"
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    preco = cond[0].get('price') if promo.get('isActive') and cond else p.get('price', 0)
                    p['preco_final'] = preco
                    p['unit_str'] = calcular_preco_unitario_nagumo(preco, desc, nome, p.get('unit'))
                    p['sort_val'] = extrair_valor_unitario(p['unit_str'])
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'])

    # Renderização Shibata
    with col1:
        st.markdown(f"<center><img src='{LOGO_SHIBATA_URL}' width='80'></center>", unsafe_allow_html=True)
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div style='display:flex; gap:10px; margin-bottom:10px;'>
                    <a href='{p['url_shibata']}' target='_blank'><img src='{img}' width='70'></a>
                    <div>
                        <a href='{p['url_shibata']}' style='text-decoration:none; color:black;'><b>{p.get('descricao')}</b></a><br>
                        <span style='font-size:1.1em;'>{p['preco_unit_str']}</span>
                    </div>
                </div><hr>""", unsafe_allow_html=True)

    # Renderização Nagumo
    with col2:
        st.markdown(f"<center><img src='{LOGO_NAGUMO_URL}' width='80'></center>", unsafe_allow_html=True)
        for p in nagumo_final:
            img = p.get('photosUrl')[0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div style='display:flex; gap:10px; margin-bottom:10px;'>
                    <a href='{p['url_nagumo']}' target='_blank'><img src='{img}' width='70'></a>
                    <div>
                        <a href='{p['url_nagumo']}' style='text-decoration:none; color:black;'><b>{p['name']}</b></a><br>
                        <b style='font-size:1.1em;'>R$ {p['preco_final']:.2f}</b><br>
                        <span style='color:gray;'>{p['unit_str']}</span>
                    </div>
                </div><hr>""", unsafe_allow_html=True)

    if not shibata_final and not nagumo_final:
        st.info("Nenhum produto encontrado nos mercados selecionados.")
