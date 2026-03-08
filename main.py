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

# --- LÓGICA DE CÁLCULO (DO CÓDIGO ANTIGO) ---

def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    q_rolos = int(match_leve.group(1)) if match_leve else None
    if not q_rolos:
        match_rolos = re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)
        q_rolos = int(match_rolos.group(1)) if match_rolos else None
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}/m"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = None
    match_unidades = re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)
    if match_unidades: qtd_unidades = int(match_unidades.group(1))

    folhas_por_unidade = None
    match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)', desc)
    if match_folhas: folhas_por_unidade = int(match_folhas.group(1))

    if qtd_unidades and folhas_por_unidade:
        total = qtd_unidades * folhas_por_unidade
        return total, preco_total / total
    return None, None

def calcular_preco_unidade_geral(descricao, preco_total):
    desc = remover_acentos(descricao)
    # Lógica para Ovos
    if 'ovo' in desc:
        match_duzia = re.search(r'1\s*d[uú]zia', desc)
        if match_duzia: return preco_total / 12, f"R$ {preco_total/12:.2f}/un (dúzia)"
        match_qtd = re.search(r'(\d+)\s*(unidades|un|ovos|c/|com)', desc)
        if match_qtd:
            qtd = int(match_qtd.group(1))
            if qtd > 0: return preco_total / qtd, f"R$ {preco_total/qtd:.2f}/un"
    
    # Lógica para Peso/Volume
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc)
    if m_kg:
        val = float(m_kg.group(1).replace(',', '.'))
        return preco_total / val, f"R$ {preco_total/val:.2f}/kg"
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc)
    if m_g:
        val = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / val, f"R$ {preco_total/val:.2f}/kg"
    
    return None, None

def destacar_folhas(texto):
    texto_low = remover_acentos(texto)
    if "folha simples" in texto_low:
        texto = re.sub(r"(folha simples)", r"<span style='color:red;'><b>\1</b></span>", texto, flags=re.IGNORECASE)
    if "folha dupla" in texto_low or "folha tripla" in texto_low:
        texto = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green;'><b>\1</b></span>", texto, flags=re.IGNORECASE)
    return texto

# --- LÓGICA DE BUSCA ---

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
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } }"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

# --- INTERFACE ---

st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

# CSS do código novo (preservado)
st.markdown("""
    <style>
        .block-container { padding-top: 0rem; padding-bottom: 15px !important; }
        footer, #MainMenu, header[data-testid="stHeader"] {visibility: hidden;}
        div, span, strong, small { font-size: 0.75rem !important; }
        img { max-width: 100px; height: auto; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6;
            border-radius: 8px; max-width: 480px; margin-left: auto; margin-right: auto;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando nos mercados..."):
        # SHIBATA
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        shibata_final = []
        vistos_sh = set()
        for p in raw_shibata:
            if p.get('id') not in vistos_sh:
                vistos_sh.add(p.get('id'))
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    p_base = float(p.get('preco') or 0)
                    p_oferta = float(oferta.get('preco_oferta')) if (p.get('em_oferta') and oferta.get('preco_oferta')) else p_base
                    
                    # Logica de Unidades e Layout
                    p['desc_html'] = destacar_folhas(desc)
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    
                    # Cálculos específicos do código antigo
                    sort_val = p_oferta
                    labels = []
                    
                    m_val, m_str = calcular_precos_papel(desc, p_oferta)
                    if m_val: 
                        labels.append(m_str)
                        sort_val = m_val
                    
                    f_total, f_preco = calcular_preco_papel_toalha(desc, p_oferta)
                    if f_preco:
                        labels.append(f"R$ {f_preco:.3f}/folha")
                        sort_val = f_preco

                    u_val, u_str = calcular_preco_unidade_geral(desc, p_oferta)
                    if u_val:
                        labels.append(u_str)
                        sort_val = u_val

                    p['sort_val'] = sort_val
                    p['unit_label'] = "<br>".join(labels)
                    p['preco_final'] = p_oferta
                    p['preco_antigo'] = float(oferta.get('preco_antigo')) if oferta.get('preco_antigo') else None
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'])

        # NAGUMO
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        
        nagumo_final = []
        vistos_nag = set()
        for p in raw_nagumo:
            if p.get('sku') not in vistos_nag:
                vistos_nag.add(p.get('sku'))
                nome, desc = p.get('name', ''), p.get('description', '')
                if all(k in remover_acentos(f"{nome} {desc}") for k in palavras_chave):
                    promo = p.get('promotion') or {}
                    p_base = float(p.get('price', 0))
                    cond = promo.get('conditions') or []
                    p_oferta = float(cond[0].get('price')) if (promo.get('isActive') and cond) else p_base
                    
                    p['desc_html'] = destacar_folhas(nome)
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{p.get('sku')}.html"
                    
                    sort_val = p_oferta
                    labels = []
                    
                    # Reaproveita lógicas de cálculo no Nagumo
                    m_val, m_str = calcular_precos_papel(f"{nome} {desc}", p_oferta)
                    if m_val: 
                        labels.append(m_str)
                        sort_val = m_val
                    
                    u_val, u_str = calcular_preco_unidade_geral(f"{nome} {desc}", p_oferta)
                    if u_val:
                        labels.append(u_str)
                        sort_val = u_val
                    else:
                        labels.append(f"R$ {p_oferta:.2f}/{p.get('unit','un')}")

                    p['sort_val'] = sort_val
                    p['unit_label'] = "<br>".join(labels)
                    p['preco_final'] = p_oferta
                    p['preco_base'] = p_base
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'])

    # --- RENDERIZAÇÃO ---

    with col1:
        st.markdown(f"<h5 style='text-align:center'><img src='{LOGO_SHIBATA_URL}' width='80'/></h5>", unsafe_allow_html=True)
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            
            # Layout de Preço com Desconto
            preco_html = f"<b>R$ {p['preco_final']:.2f}</b>"
            if p['preco_antigo'] and p['preco_antigo'] > p['preco_final']:
                desc_perc = round(100 * (p['preco_antigo'] - p['preco_final']) / p['preco_antigo'])
                preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b> <span style='color:red;'>({desc_perc}% OFF)</span></div><div style='color:gray;text-decoration:line-through;'>R$ {p['preco_antigo']:.2f}</div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:6px 6px 0 0; border:1px solid #eee;'/>
                        <img src='{LOGO_SHIBATA_URL}' width='80' style='border-top:1.5px solid black; padding:2px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'>{p['desc_html']}</a>
                        <div style='margin-top:4px;'>{preco_html}</div>
                        <div style='color:gray; font-size:0.7em;'>{p['unit_label']}</div>
                    </div>
                </div><hr class='product-separator'/>
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"<h5 style='text-align:center'><img src='{LOGO_NAGUMO_URL}' width='80'/></h5>", unsafe_allow_html=True)
        for p in nagumo_final:
            imgs = p.get('photosUrl')
            img = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            
            preco_html = f"<b>R$ {p['preco_final']:.2f}</b>"
            if p['preco_base'] > p['preco_final']:
                desc_perc = round(100 * (p['preco_base'] - p['preco_final']) / p['preco_base'])
                preco_html = f"<div><b>R$ {p['preco_final']:.2f}</b> <span style='color:red;'>({desc_perc}% OFF)</span></div><div style='color:gray;text-decoration:line-through;'>R$ {p['preco_base']:.2f}</div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:6px 6px 0 0; border:1px solid #eee;'/>
                        <img src='{LOGO_NAGUMO_URL}' width='80' style='border-top:1.5px solid #eee; padding:2px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'>{p['desc_html']}</a>
                        <div style='margin-top:4px;'>{preco_html}</div>
                        <div style='color:gray; font-size:0.7em;'>{p['unit_label']}</div>
                        <div style='color:gray; font-size:0.6em;'>Estoque: {p.get('stock',0)}</div>
                    </div>
                </div><hr class='product-separator'/>
            """, unsafe_allow_html=True)

    components.html(f"<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
