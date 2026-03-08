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
    # Adiciona plural/singular simples para melhorar a busca
    if termo.endswith("s"): variantes.add(termo[:-1])
    else: variantes.add(termo + "s")
    return list(variantes)

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- LÓGICA DE CÁLCULO E FORMATAÇÃO (RESTAURADA) ---
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
    # KG
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # Gramas
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # Litros
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)) else None
    folhas_por_unidade = int(m.group(1)) if (m := re.search(r'(\d+)\s*(folhas|toalhas)(?:\s*cada)?', desc)) else None
    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return total_folhas, preco_total / total_folhas if total_folhas else None
    return None, None

def formatar_preco_shibata(preco_total, qtd, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

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
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price priceBeforeTaxes } } } } }"
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
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 480px; margin-left: auto; margin-right: auto; background: transparent;
        }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    # Melhoria na filtragem: usa o termo limpo para validar a presença
    palavras_filtro = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando nos mercados..."):
        # --- PROCESSAMENTO SHIBATA ---
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        vistos_shibata = set()
        shibata_final = []
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_shibata and p.get("disponivel", True):
                vistos_shibata.add(pid)
                desc_p = p.get('descricao', '')
                desc_limpa = remover_acentos(desc_p)
                
                # CORREÇÃO DA LÓGICA DE FILTRAGEM (MAÇÃ GALA)
                # Verifica se as palavras principais estão contidas na descrição
                if all(p_filtro in desc_limpa for p_filtro in palavras_filtro):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc_p)}"
                    p['preco_str'] = formatar_preco_shibata(preco_final, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['preco_final_val'] = preco_final
                    
                    # Cálculo de ordenação e unidade
                    val_metro, _ = calcular_precos_papel(desc_p, preco_final)
                    val_unidade, _ = calcular_preco_unidade(desc_p, preco_final)
                    p['sort_val'] = val_metro or val_unidade or preco_final
                    
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'] or 999)

    # --- EXIBIÇÃO COLUNA 1 (SHIBATA) ---
    with col1:
        st.markdown(f"""<h5 style="text-align: center;"><img src="{LOGO_SHIBATA_URL}" width="80" style="background-color: white; border-radius: 4px; padding: 3px;"/></h5>""", unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(shibata_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            descricao = p.get('descricao', '')
            desc_visual = descricao
            preco_info_extra = ""
            preco_total = p['preco_final_val']

            # Cores para Papel Higiênico
            if 'papel higienico' in remover_acentos(descricao):
                desc_visual = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", desc_visual, flags=re.IGNORECASE)
                desc_visual = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", desc_visual, flags=re.IGNORECASE)

            # Cálculos de unidade/metro/folha
            t_folhas, p_folha = calcular_preco_papel_toalha(descricao, preco_total)
            if t_folhas and p_folha:
                preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>R$ {p_folha:.3f}/folha</div>"
            else:
                _, p_m_str = calcular_precos_papel(descricao, preco_total)
                if p_m_str: preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>{p_m_str}</div>"
                else:
                    _, p_u_str = calcular_preco_unidade(descricao, preco_total)
                    if p_u_str: preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>{p_u_str}</div>"

            # Preço e Desconto
            oferta = p.get('oferta') or {}
            if p.get('em_oferta') and oferta.get('preco_antigo'):
                p_antigo = float(oferta.get('preco_antigo'))
                perc = round(100 * (p_antigo - preco_total) / p_antigo)
                preco_html = f"<div><b>{p['preco_str']}</b> <span style='color:red; font-weight:bold;'>({perc}% OFF)</span></div>"
                preco_html += f"<div><span style='color:gray; text-decoration:line-through;'>R$ {p_antigo:.2f}</span></div>"
            else:
                preco_html = f"<div><b>{p['preco_str']}</b></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='background-color: white; border-radius: 6px 0 0 6px;'/>
                        <img src='{LOGO_SHIBATA_URL}' width='80' style='background-color: white; border-top: 1.5px solid black; padding: 2px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{desc_visual}</b></a>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                        {preco_info_extra}
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # --- COLUNA 2 (NAGUMO) ---
    with col2:
        st.markdown(f"""<h5 style="text-align: center;"><img src="{LOGO_NAGUMO_URL}" width="80" style="border-radius: 6px; border: 1.5px solid white;"/></h5>""", unsafe_allow_html=True)
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        vistos_n = set(); nagumo_f = []
        for n in raw_nagumo:
            sku = n.get('sku')
            if sku and sku not in vistos_n:
                vistos_n.add(sku); nome = n.get('name', '')
                if all(k in remover_acentos(nome) for k in palavras_filtro):
                    promo = n.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    p_normal = n.get('price', 0)
                    p_final = cond[0].get('price') if (promo.get('isActive') and cond) else p_normal
                    n['preco_final'] = p_final; n['url_final'] = f"https://www.nagumo.com.br/p/{slugify(nome)}-{sku}.html"
                    # Cálculo unitário simples para ordenação Nagumo
                    _, p_u_val = calcular_preco_unidade(nome, p_final)
                    n['sort_val'] = p_u_val or p_final
                    nagumo_f.append(n)
        
        for n in sorted(nagumo_f, key=lambda x: x['sort_val']):
            img_n = n.get('photosUrl')[0] if n.get('photosUrl') else DEFAULT_IMAGE_URL
            titulo = n['name']
            # Aplicação de cores papel higiênico Nagumo
            if 'papel higienico' in remover_acentos(titulo):
                titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{n['url_final']}' target='_blank' class='product-image'><img src='{img_n}' width='80'/><img src='{LOGO_NAGUMO_URL}' width='80'/></a>
                    <div class='product-info'>
                        <a href='{n['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{titulo}</b></a><br>
                        <b>R$ {n['preco_final']:.2f}</b>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
