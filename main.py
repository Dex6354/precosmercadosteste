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

# --- LÓGICA DE CÁLCULO (RESTAURADA DO CÓDIGO ANTIGO) ---
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

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    m_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if m_l:
        litros = float(m_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"
    m_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if m_ml:
        litros = float(m_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    m_unidades = re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)
    qtd_unidades = int(m_unidades.group(1)) if m_unidades else None
    m_folhas = re.search(r'(\d+)\s*(folhas|toalhas)', desc)
    folhas_por_unidade = int(m_folhas.group(1)) if m_folhas else None
    
    if qtd_unidades and folhas_por_unidade:
        total = qtd_unidades * folhas_por_unidade
        return total, preco_total / total
    if folhas_por_unidade:
        return folhas_por_unidade, preco_total / folhas_por_unidade
    return None, None

def formatar_preco_shibata_label(preco_total, qtd, unidade):
    if not unidade or unidade.lower() == "grande": return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

# --- LÓGICA SHIBATA (BUSCA AMPLIADA) ---
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if r.status_code == 200:
            return r.json().get('data', {}).get('produtos', [])
    except: pass
    return []

# --- LÓGICA NAGUMO ---
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

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
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
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termo_norm = remover_acentos(termo)
    termos_busca = gerar_formas_variantes(termo_norm)
    palavras_chave = termo_norm.split()

    with st.spinner("🔍 Buscando nos mercados..."):
        # --- PROCESSAMENTO SHIBATA (LÓGICA RESTAURADA) ---
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            # Busca em até 10 páginas para garantir resultados
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 11)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        vistos_shibata = set()
        shibata_final = []
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_shibata and p.get('disponivel', True):
                vistos_shibata.add(pid)
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    # Preço
                    oferta = p.get('oferta') or {}
                    p_base = float(p.get('preco') or 0)
                    p_oferta = float(oferta.get('preco_oferta')) if (p.get('em_oferta') and oferta.get('preco_oferta')) else None
                    preco_final = p_oferta if p_oferta else p_base
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    p['preco_label'] = formatar_preco_shibata_label(preco_final, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    
                    # Lógica de Ordenação Restaurada
                    sort_val = float('inf')
                    extra_label = ""
                    
                    # 1. Papel Higiênico
                    if 'papel higienico' in termo_norm:
                        v, label = calcular_precos_papel(desc, preco_final)
                        if v: sort_val, extra_label = v, label
                    # 2. Papel Toalha
                    elif 'papel toalha' in termo_norm:
                        folhas, v = calcular_preco_papel_toalha(desc, preco_final)
                        if v: sort_val, extra_label = v, f"R$ {v:.3f}/folha ({folhas} fls)"
                    # 3. Ovos
                    elif 'ovo' in termo_norm:
                        m_ovo = re.search(r'(\d+)\s*(unidades|un|ovos|c/|com)', desc.lower())
                        qtd = int(m_ovo.group(1)) if m_ovo else (12 if 'duzia' in remover_acentos(desc) else None)
                        if qtd: 
                            sort_val = preco_final / qtd
                            extra_label = f"R$ {sort_val:.2f}/un"
                    # 4. Peso/Volume (KG/L)
                    else:
                        v, label = calcular_preco_unidade(desc, preco_final)
                        if v: sort_val, extra_label = v, label
                    
                    # Fallback de ordenação pelo preço final se não houver unidade específica
                    if sort_val == float('inf'): sort_val = preco_final
                    
                    p['sort_val'] = sort_val
                    p['extra_info'] = extra_label
                    shibata_final.append(p)
        
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'])

        # --- PROCESSAMENTO NAGUMO (URL CORRIGIDA) ---
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        
        vistos_nagumo = set()
        nagumo_final = []
        for p in raw_nagumo:
            sku = p.get('sku')
            if sku and sku not in vistos_nagumo:
                vistos_nagumo.add(sku)
                nome, desc = p.get('name', ''), p.get('description', '')
                if all(k in remover_acentos(f"{nome} {desc}") for k in palavras_chave):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    p_final = cond[0].get('price') if (promo.get('isActive') and cond) else p.get('price', 0)
                    
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
                    
                    # Unidade Nagumo
                    fonte = f"{nome} {desc}".lower()
                    m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo|g|gramas?|l|litros?|ml)", fonte)
                    s_val = p_final
                    u_label = f"R$ {p_final:.2f}/{p.get('unit') or 'un'}"
                    
                    if m_kg:
                        val = float(m_kg.group(1).replace(',', '.'))
                        und = m_kg.group(2)
                        if 'g' in und and 'kg' not in und: val /= 1000
                        if 'ml' in und: val /= 1000
                        if val > 0:
                            s_val = p_final / val
                            u_label = f"R$ {s_val:.2f}/" + ("kg" if 'g' in und else "L")
                    
                    p['sort_val'] = s_val
                    p['unit_label'] = u_label
                    p['preco_final'] = p_final
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'])

    # --- EXIBIÇÃO ---
    with col1:
        st.markdown(f"<center><img src='{LOGO_SHIBATA_URL}' width='80'></center>", unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(shibata_final)} produtos</small>", unsafe_allow_html=True)
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:4px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'><b>{p['descricao']}</b></a><br>
                        <b>{p['preco_label']}</b><br>
                        <span style='color:gray; font-size:0.7em;'>{p['extra_info']}</span>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"<center><img src='{LOGO_NAGUMO_URL}' width='80'></center>", unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(nagumo_final)} produtos</small>", unsafe_allow_html=True)
        for p in nagumo_final:
            imgs = p.get('photosUrl')
            img = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:4px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'><b>{p['name']}</b></a><br>
                        <span style='font-size:1rem;'><b>R$ {p['preco_final']:.2f}</b></span><br>
                        <span style='color:gray; font-size:0.7em;'>{p['unit_label']}</span>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(f"<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
