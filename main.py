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

# --- FUNÇÕES UTILITÁRIAS COMUNS ---
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

# --- LÓGICA DE CÁLCULO ---
def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    q_rolos = int(match_leve.group(1)) if match_leve else (
        int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)) else None
    )
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
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
    qtd_unidades = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)) else None
    folhas_por_unidade = int(m.group(1)) if (m := re.search(r'(\d+)\s*(folhas|toalhas)(?:\s*cada)?', desc)) else None
    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return total_folhas, preco_total / total_folhas if total_folhas else None
    if folhas_por_unidade: return folhas_por_unidade, preco_total / folhas_por_unidade
    return None, None

def formatar_preco_shibata(preco_total, qtd, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

# Lógica Nagumo
def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_completo = f"{remover_acentos(nome.lower())} {remover_acentos(descricao.lower())}"
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        rolos, folhas = int(match.group(1)), int(match.group(3))
        return rolos, folhas, rolos * folhas, f"{rolos} un, {folhas} folhas"
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()
    if contem_papel_toalha(texto_completo):
        _, _, total_folhas, _ = extrair_info_papel_toalha(nome, descricao)
        if total_folhas: return f"R$ {preco_valor / total_folhas:.3f}/folha"
    
    # Busca por padrões de peso/volume
    fontes = [nome.lower(), descricao.lower()]
    for fonte in fontes:
        m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo|g|grama|l|litro|ml)", fonte)
        if m_kg:
            val = float(m_kg.group(1).replace(',', '.'))
            uni = m_kg.group(2)
            if 'g' in uni and 'k' not in uni: return f"R$ {preco_valor/(val/1000):.2f}/kg"
            if 'ml' in uni: return f"R$ {preco_valor/(val/1000):.2f}/L"
            if uni in ['kg', 'l']: return f"R$ {preco_valor/val:.2f}/{uni}"
    return "Sem unidade"

def extrair_valor_unitario(preco_unitario):
    match = re.search(r"R\$ (\d+[.,]?\d*)", preco_unitario)
    return float(match.group(1).replace(',', '.')) if match else float('inf')

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
    payload = {
        "operationName": "SearchProducts",
        "variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50, "search": [{"query": term}]}},
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""<style>
    .block-container { padding-top: 1rem; }
    div, span, strong, small { font-size: 0.75rem !important; }
    [data-testid="stColumn"] { border: 1px solid #f0f2f6; border-radius: 8px; padding: 10px; max-height: 85vh; overflow-y: auto; }
</style>""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Comparador de Preços</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 O que você procura?", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_filtro = remover_acentos(termo).split()

    with st.spinner("🔍 Sincronizando preços..."):
        # SHIBATA - Lógica de busca ampliada
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=10) as exe:
            # Aumentado para 8 páginas para garantir mais resultados
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 9)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        vistos_shibata = set()
        shibata_final = []
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_shibata and p.get("disponivel", True):
                vistos_shibata.add(pid)
                desc = remover_acentos(p.get('descricao', ''))
                # Filtro mais flexível: se contiver a primeira palavra principal ou a maioria das palavras
                if any(word in desc for word in palavras_filtro):
                    oferta = p.get('oferta') or {}
                    preco_final = float(oferta.get('preco_oferta')) if (p.get('em_oferta') and oferta.get('preco_oferta')) else float(p.get('preco') or 0)
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(p.get('descricao'))}"
                    p['preco_str'] = formatar_preco_shibata(preco_final, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['preco_final'] = preco_final
                    
                    # Ordenação
                    val_metro, _ = calcular_precos_papel(p.get('descricao'), preco_final)
                    val_unidade, _ = calcular_preco_unidade(p.get('descricao'), preco_final)
                    p['sort_val'] = val_metro or val_unidade or preco_final
                    shibata_final.append(p)
        
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'])

        # NAGUMO
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        vistos_nagumo = set()
        nagumo_final = []
        for p in raw_nagumo:
            sku = p.get('sku')
            if sku and sku not in vistos_nagumo:
                vistos_nagumo.add(sku)
                nome_desc = remover_acentos(f"{p.get('name')} {p.get('description')}")
                if any(word in nome_desc for word in palavras_filtro):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    p['preco_normal'] = p.get('price', 0)
                    p['preco_final'] = cond[0].get('price') if (promo.get('isActive') and cond) else p['preco_normal']
                    p['url_final'] = f"https://www.nagumo.com.br/p/{sku}"
                    p['unit_label'] = calcular_preco_unitario_nagumo(p['preco_final'], p.get('description', ''), p['name'])
                    p['sort_val'] = extrair_valor_unitario(p['unit_label'])
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'])

    # EXIBIÇÃO
    with col1:
        st.image(LOGO_SHIBATA_URL, width=100)
        st.caption(f"{len(shibata_final)} resultados")
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div style='display: flex; gap: 10px; margin-bottom: 10px;'>
                    <img src='{img}' width='60' style='border-radius: 5px; background: white;'>
                    <div>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:#333;'><b>{p.get('descricao')}</b></a><br>
                        <span style='color: green; font-weight: bold;'>{p['preco_str']}</span>
                    </div>
                </div><hr style='margin: 5px 0; opacity: 0.2;'>
            """, unsafe_allow_html=True)

    with col2:
        st.image(LOGO_NAGUMO_URL, width=100)
        st.caption(f"{len(nagumo_final)} resultados")
        for p in nagumo_final:
            imgs = p.get('photosUrl')
            img = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div style='display: flex; gap: 10px; margin-bottom: 10px;'>
                    <img src='{img}' width='60' style='border-radius: 5px; background: white;'>
                    <div>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:#333;'><b>{p.get('name')}</b></a><br>
                        <span style='color: green; font-weight: bold;'>R$ {p['preco_final']:.2f}</span><br>
                        <small style='color: gray;'>{p['unit_label']}</small>
                    </div>
                </div><hr style='margin: 5px 0; opacity: 0.2;'>
            """, unsafe_allow_html=True)

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
