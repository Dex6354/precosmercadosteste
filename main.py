import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES UTILITÁRIAS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    variantes = {termo}
    if termo.endswith("s"): variantes.add(termo[:-1])
    else: variantes.add(termo + "s")
    return list(variantes)

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    # KG
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # GRAMAS
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # LITROS
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    # ML
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return ""

def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    q_rolos = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)) else None
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return ""

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)) else None
    folhas_por_unidade = int(m.group(1)) if (m := re.search(r'(\d+)\s*(folhas|toalhas)(?:\s*cada)?', desc)) else None
    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return f"R$ {preco_total / total_folhas:.3f}".replace('.', ',') + "/folha"
    return ""

# --- REQUISIÇÕES ---
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if r.status_code == 200: return r.json().get('data', {}).get('produtos', [])
    except: pass
    return []

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {"Content-Type": "application/json", "Origin": "https://www.nagumo.com", "User-Agent": "Mozilla/5.0"}
    payload = {
        "operationName": "SearchProducts",
        "variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50, "search": [{"query": term}], "filters": {}}},
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

# --- INTERFACE ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer, #MainMenu, header[data-testid="stHeader"] { visibility: hidden; display: none; }
        div, span, strong, small { font-size: 0.75rem !important; }
        .product-container { display: flex; align-items: center; gap: 10px; margin-bottom: 0px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; text-decoration: none; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 480px; margin-left: auto; margin-right: auto; background: transparent;
        }
        .img-stacked { background-color: white; display: block; width: 80px; }
        .img-main { border-top-left-radius: 6px; border-top-right-radius: 6px; }
        .img-logo { border-top: 1.5px solid black; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; padding: 3px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando..."):
        # SHIBATA
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        shibata_final = []
        vistos_s = set()
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_s:
                vistos_s.add(pid)
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    p['preco_final'] = float(oferta.get('preco_oferta')) if (p.get('em_oferta') and oferta.get('preco_oferta')) else float(p.get('preco') or 0)
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    shibata_final.append(p)

        # NAGUMO
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        nagumo_final = []
        vistos_n = set()
        for p in raw_nagumo:
            sku = p.get('sku')
            if sku and sku not in vistos_n:
                vistos_n.add(sku)
                n, d = p.get('name', ''), p.get('description', '')
                if all(k in remover_acentos(f"{n} {d}") for k in palavras_chave):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    p['preco_normal'] = p.get('price', 0)
                    p['preco_final'] = cond[0].get('price') if (promo.get('isActive') and cond) else p['preco_normal']
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(n)}-{sku}.html"
                    nagumo_final.append(p)

    # --- RENDERIZAÇÃO ---
    for col, lista, logo, mercado in [(col1, shibata_final, LOGO_SHIBATA_URL, "Shibata"), (col2, nagumo_final, LOGO_NAGUMO_URL, "Nagumo")]:
        with col:
            st.markdown(f"<h5 style='text-align:center;'><img src='{logo}' width='80'/></h5>", unsafe_allow_html=True)
            for p in lista:
                if mercado == "Shibata":
                    img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
                    titulo = p['descricao']
                    oferta = p.get('oferta') or {}
                    
                    if p.get('em_oferta') and oferta.get('preco_antigo'):
                        p_ant = float(oferta.get('preco_antigo'))
                        off = round(100 * (p_ant - p['preco_final']) / p_ant)
                        preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b> <span style='color:red;'>({off}% OFF)</span></div><div style='text-decoration:line-through; color:gray;'>R$ {p_ant:.2f}</div>"
                    else:
                        preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b></div>"
                    
                    # CÁLCULO UNITÁRIO SHIBATA (FORÇADO AQUI)
                    extra_label = ""
                    if "papel toalha" in remover_acentos(titulo): extra_label = calcular_preco_papel_toalha(titulo, p['preco_final'])
                    elif "papel higi" in remover_acentos(titulo): extra_label = calcular_precos_papel(titulo, p['preco_final'])
                    else: extra_label = calcular_preco_unidade(titulo, p['preco_final'])
                
                else: # NAGUMO
                    img = p.get('photosUrl')[0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
                    titulo = p['name']
                    if p['preco_final'] < p['preco_normal']:
                        off = round(100 * (p['preco_normal'] - p['preco_final']) / p['preco_normal'])
                        preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b> <span style='color:red;'>({off}% OFF)</span></div><div style='text-decoration:line-through; color:gray;'>R$ {p['preco_normal']:.2f}</div>"
                    else:
                        preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b></div>"
                    
                    # CÁLCULO UNITÁRIO NAGUMO (SIMPLIFICADO)
                    extra_label = calcular_preco_unidade(f"{titulo} {p.get('description','')}", p['preco_final'])

                # Formatação de papel higiênico
                if "papel higi" in remover_acentos(titulo):
                    titulo = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", titulo, flags=re.IGNORECASE)
                    titulo = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", titulo, flags=re.IGNORECASE)

                st.markdown(f"""
                    <div class='product-container'>
                        <a href='{p['url_final']}' target='_blank' class='product-image'>
                            <img src='{img}' class='img-stacked img-main'/>
                            <img src='{logo}' class='img-stacked img-logo'/>
                        </a>
                        <div class='product-info'>
                            <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{titulo}</b></a>
                            {preco_html}
                            <div style='color:gray;'>{extra_label}</div>
                        </div>
                    </div><hr class='product-separator'/>
                """, unsafe_allow_html=True)

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
