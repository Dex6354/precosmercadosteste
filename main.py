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
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    # KG
    match_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if match_kg:
        peso = float(match_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # Gramas
    match_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if match_g:
        peso = float(match_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # Litros
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    # ML
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = None
    match_unidades = re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)
    if match_unidades: qtd_unidades = int(match_unidades.group(1))

    folhas_por_unidade = None
    match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)\s*cada', desc)
    if not match_folhas: match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)', desc)
    if match_folhas: folhas_por_unidade = int(match_folhas.group(1))

    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        return folhas_leve, preco_total / folhas_leve if folhas_leve else None

    if qtd_unidades and folhas_por_unidade:
        total = qtd_unidades * folhas_por_unidade
        return total, preco_total / total
    
    if folhas_por_unidade:
        return folhas_por_unidade, preco_total / folhas_por_unidade

    return None, None

def formatar_preco_unidade_personalizado(preco_total, quantidade, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    unidade = unidade.lower()
    if quantidade and quantidade != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(quantidade).replace('.', ',')}{unidade}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{unidade}"

# --- BUSCAS ---

def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        response = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {}).get('produtos', [])
            return [p for p in data if p.get("disponivel", True)]
    except: return []
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
        .block-container { padding-top: 0rem; padding-right: 47px !important; padding-bottom: 15px !important; }
        footer, #MainMenu, header[data-testid="stHeader"] {visibility: hidden; display: none;}
        div, span, strong, small { font-size: 0.75rem !important; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6;
            border-radius: 8px; max-width: 480px; margin: 0 auto 20px auto;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; }
        input[type="text"] { font-size: 0.8rem !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip().lower()
termos_expandidos = gerar_formas_variantes(remover_acentos(termo))

if termo:
    col1, col2 = st.columns(2)
    termo_sem_acento = remover_acentos(termo)
    palavras_termo = termo_sem_acento.split()

    with st.spinner("🔍 Buscando produtos..."):
        # --- SHIBATA ---
        produtos_shibata_raw = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(buscar_pagina_shibata, t, p) for t in termos_expandidos for p in range(1, 6)]
            for f in as_completed(futures): produtos_shibata_raw.extend(f.result())

        ids_vistos = set()
        produtos_shibata_processados = []
        for p in produtos_shibata_raw:
            if p.get('id') in ids_vistos: continue
            ids_vistos.add(p.get('id'))
            
            nome_completo = f"{p.get('descricao', '')} {p.get('nome', '')}"
            if not all(palavra in remover_acentos(nome_completo) for palavra in palavras_termo): continue

            preco_base = float(p.get('preco') or 0)
            oferta = p.get('oferta') or {}
            em_oferta = p.get('em_oferta', False)
            preco_final = float(oferta.get('preco_oferta')) if (em_oferta and oferta.get('preco_oferta')) else preco_base
            
            p['preco_final_calc'] = preco_final
            p['url_link'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(p.get('descricao', 'p'))}"
            
            # Cálculo de Unidade
            _, p_un_str = calcular_preco_unidade(p.get('descricao', ''), preco_final)
            _, p_met_str = calcular_precos_papel(p.get('descricao', ''), preco_final)
            folhas, p_folha_val = calcular_preco_papel_toalha(p.get('descricao', ''), preco_final)
            
            p['extra_info'] = []
            if p_un_str: p['extra_info'].append(p_un_str)
            if p_met_str: p['extra_info'].append(p_met_str)
            if p_folha_val: p['extra_info'].append(f"R$ {p_folha_val:.3f}/folha")
            p['folhas_count'] = folhas
            
            produtos_shibata_processados.append(p)

        # --- NAGUMO ---
        produtos_nagumo_raw = []
        for t in termos_expandidos: produtos_nagumo_raw.extend(buscar_nagumo(t))
        
        skus_vistos = set()
        produtos_nagumo_processados = []
        for p in produtos_nagumo_raw:
            sku = p.get('sku')
            if not sku or sku in skus_vistos: continue
            skus_vistos.add(sku)
            
            nome, desc = p.get('name', ''), p.get('description', '')
            if not all(k in remover_acentos(f"{nome} {desc}") for k in palavras_termo): continue

            promo = p.get('promotion') or {}
            cond = promo.get('conditions') or []
            preco_final = cond[0].get('price') if (promo.get('isActive') and cond) else p.get('price', 0)
            
            p['preco_final_calc'] = preco_final
            p['url_link'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
            
            # Cálculo de Unidade (Mesma lógica do Shibata)
            _, p_un_str = calcular_preco_unidade(f"{nome} {desc}", preco_final)
            _, p_met_str = calcular_precos_papel(f"{nome} {desc}", preco_final)
            folhas, p_folha_val = calcular_preco_papel_toalha(f"{nome} {desc}", preco_final)
            
            p['extra_info'] = []
            if p_un_str: p['extra_info'].append(p_un_str)
            if p_met_str: p['extra_info'].append(p_met_str)
            if p_folha_val: p['extra_info'].append(f"R$ {p_folha_val:.3f}/folha")
            p['folhas_count'] = folhas

            produtos_nagumo_processados.append(p)

    # --- RENDERIZAÇÃO ---

    def render_coluna(titulo_logo, produtos, is_shibata=True):
        st.markdown(f'<h5 style="text-align:center;"><img src="{titulo_logo}" width="80" style="background:white; border-radius:4px; padding:3px; border:1px solid #ddd;"/></h5>', unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(produtos)} produto(s).</small>", unsafe_allow_html=True)
        
        # Ordenação simples por preço final
        produtos_ord = sorted(produtos, key=lambda x: x['preco_final_calc'])

        for p in produtos_ord:
            nome = p.get('descricao') if is_shibata else p.get('name')
            img = p.get('imagem') if is_shibata else (p.get('photosUrl')[0] if p.get('photosUrl') else "")
            img_url = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{img}" if (is_shibata and img) else (img or DEFAULT_IMAGE_URL)
            
            # Lógica de Cores para Papel
            nome_html = nome
            if 'papel higienico' in remover_acentos(nome):
                nome_html = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", nome_html, flags=re.IGNORECASE)
                nome_html = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", nome_html, flags=re.IGNORECASE)
            
            if p.get('folhas_count'):
                nome_html += f" <span style='color:gray;'>({p['folhas_count']} folhas)</span>"

            # Preço e Ofertas
            preco_str = f"R$ {p['preco_final_calc']:.2f}".replace('.', ',')
            preco_html = f"<b>{preco_str}</b>"
            
            if is_shibata and p.get('em_oferta'):
                antigo = (p.get('oferta') or {}).get('preco_antigo')
                if antigo:
                    desc = round(100 * (float(antigo) - p['preco_final_calc']) / float(antigo))
                    preco_html = f"<div>{preco_html} <span style='color:red;'>( {desc}% OFF )</span></div>"
                    preco_html += f"<div style='text-decoration:line-through; color:gray;'>R$ {float(antigo):.2f}</div>".replace('.', ',')

            extras = "".join([f"<div style='color:gray;'>{info}</div>" for info in p['extra_info']])

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_link']}' target='_blank' style='text-decoration:none;'>
                        <img src='{img_url}' width='80' style='border-radius:4px 4px 0 0;'/>
                        <img src='{titulo_logo}' width='80' style='border-top:1px solid #eee; padding:2px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_link']}' target='_blank' style='text-decoration:none; color:black;'><strong>{nome_html}</strong></a>
                        <div style='font-size:1rem; margin-top:4px;'>{preco_html}</div>
                        {extras}
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    with col1: render_coluna(LOGO_SHIBATA_URL, produtos_shibata_processados, True)
    with col2: render_coluna(LOGO_NAGUMO_URL, produtos_nagumo_processados, False)
