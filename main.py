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
    # Normaliza o termo base antes de gerar variantes
    termo_limpo = remover_acentos(termo)
    variantes = {termo_limpo}
    if termo_limpo.endswith("s"): 
        variantes.add(termo_limpo[:-1])
    else: 
        variantes.add(termo_limpo + "s")
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
    
    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        return folhas_leve, preco_total / folhas_leve if folhas_leve else None

    match_leve_pague = re.findall(r'(\d+)', desc)
    folhas_leve = max(int(n) for n in match_leve_pague) if 'leve' in desc and 'folhas' in desc and match_leve_pague else None

    m_kit = re.search(r'unidades por kit[:\- ]+(\d+)', desc)
    m_rolo = re.search(r'quantidade de folhas por (?:rolo|unidade)[:\- ]+(\d+)', desc)
    if m_kit and m_rolo:
        total_folhas = int(m_kit.group(1)) * int(m_rolo.group(1))
        return total_folhas, preco_total / total_folhas if total_folhas else None

    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return total_folhas, preco_total / total_folhas if total_folhas else None

    if folhas_por_unidade: return folhas_por_unidade, preco_total / folhas_por_unidade
    if folhas_leve: return folhas_leve, preco_total / folhas_leve
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
    texto_nome = remover_acentos(nome.lower())
    texto_completo = f"{texto_nome} {remover_acentos(descricao.lower())}"

    for texto in [texto_nome, texto_completo]:
        match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto)
        if match:
            rolos, folhas_por_rolo = int(match.group(1)), int(match.group(3))
            return rolos, folhas_por_rolo, rolos * folhas_por_rolo, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"
        match = re.search(r'(\d+)\s*(folhas|toalhas)', texto)
        if match: return None, None, int(match.group(1)), f"{match.group(1)} {match.group(2)}"
    
    m_un = re.search(r"(\d+)\s*(un|unidades?)", texto_completo)
    if m_un: return None, None, int(m_un.group(1)), f"{m_un.group(1)} unidades"
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()
    if contem_papel_toalha(texto_completo):
        rolos, folhas, total_folhas, txt = extrair_info_papel_toalha(nome, descricao)
        if total_folhas and total_folhas > 0: return f"R$ {preco_valor / total_folhas:.3f}/folha"
        return "Preço por folha: n/d"

    if "papel higi" in texto_completo:
        m_rolos = re.search(r"(leve\s*0*|lv?\s*0*|lv?|l\s*0*|c/\s*0*)(\d+)", texto_completo)
        if not m_rolos: m_rolos = re.search(r"(\d+)\s*(rolos?|un|unidades?)", texto_completo)
        m_metros = re.search(r"(\d+[.,]?\d*)\s*(m|metros?|mt)", texto_completo)
        if m_rolos and m_metros:
            try:
                rolos = int(m_rolos.group(2) if m_rolos.lastindex > 1 else m_rolos.group(1))
                metros = float(m_metros.group(1).replace(',', '.'))
                if rolos > 0 and metros > 0: return f"R$ {preco_valor / rolos / metros:.3f}/m"
            except: pass

    fontes = [descricao.lower(), nome.lower()]
    for fonte in fontes:
        match_g = re.search(r"(\d+[.,]?\d*)\s*(g|gramas?)", fonte)
        if match_g and float(match_g.group(1).replace(',', '.')) > 0: return f"R$ {preco_valor / (float(match_g.group(1).replace(',', '.')) / 1000):.2f}/kg"
        match_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo)", fonte)
        if match_kg and float(match_kg.group(1).replace(',', '.')) > 0: return f"R$ {preco_valor / float(match_kg.group(1).replace(',', '.')):.2f}/kg"
        match_ml = re.search(r"(\d+[.,]?\d*)\s*(ml|mililitros?)", fonte)
        if match_ml and float(match_ml.group(1).replace(',', '.')) > 0: return f"R$ {preco_valor / (float(match_ml.group(1).replace(',', '.')) / 1000):.2f}/L"
        match_l = re.search(r"(\d+[.,]?\d*)\s*(l|litros?)", fonte)
        if match_l and float(match_l.group(1).replace(',', '.')) > 0: return f"R$ {preco_valor / float(match_l.group(1).replace(',', '.')):.2f}/L"
        match_un = re.search(r"(\d+[.,]?\d*)\s*(un|unidades?)", fonte)
        if match_un and float(match_un.group(1).replace(',', '.')) > 0: return f"R$ {preco_valor / float(match_un.group(1).replace(',', '.')):.2f}/un"

    if unidade_api:
        u = unidade_api.lower()
        if u == 'kg': return f"R$ {preco_valor:.2f}/kg"
        elif u == 'g': return f"R$ {preco_valor * 1000:.2f}/kg"
        elif u == 'l': return f"R$ {preco_valor:.2f}/L"
        elif u == 'ml': return f"R$ {preco_valor * 1000:.2f}/L"
        elif u == 'un': return f"R$ {preco_valor:.2f}/un"
    return "Sem unidade"

def extrair_valor_unitario(preco_unitario):
    match = re.search(r"R\$ (\d+[.,]?\d*)", preco_unitario)
    if match: return float(match.group(1).replace(',', '.'))
    return float('inf')

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
        .info-cinza { color: gray; font-size: 0.8rem; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 480px; margin-left: auto; margin-right: auto; background: transparent;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-track { background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; border: 1px solid transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb:hover { background-color: white; }
        .block-container { padding-right: 47px !important; padding-bottom: 15px !important; margin-bottom: 15px !important; }
        input[type="text"] { font-size: 0.8rem !important; }
        [data-testid="stColumn"] { margin-bottom: 20px; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(termo)
    # Palavras-chave para filtro normalizadas (sem acento)
    palavras_chave_filtro = remover_acentos(termo).split()

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
                desc = p.get('descricao', '')
                # Normalização da descrição para comparação flexível
                desc_normalizada = remover_acentos(desc)
                
                if all(k in desc_normalizada for k in palavras_chave_filtro):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    
                    unidade_sigla = p.get('unidade_sigla')
                    if unidade_sigla and unidade_sigla.lower() == "grande": unidade_sigla = None
                    p['preco_str'] = formatar_preco_shibata(preco_final, p.get('quantidade_unidade_diferente'), unidade_sigla)
                    p['preco_final'] = preco_final
                    
                    val_metro, _ = calcular_precos_papel(desc, preco_final)
                    _, val_folha = calcular_preco_papel_toalha(desc, preco_final)
                    val_unidade, _ = calcular_preco_unidade(desc, preco_final)
                    
                    if 'papel toalha' in desc_normalizada and val_folha: p['sort_val'] = val_folha
                    elif 'papel higienico' in desc_normalizada and val_metro: p['sort_val'] = val_metro
                    else: p['sort_val'] = val_unidade or preco_final
                    
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'] or 999)

        # --- PROCESSAMENTO NAGUMO ---
        raw_nagumo = []
        for t in termos_busca: raw_nagumo.extend(buscar_nagumo(t))
        
        vistos_nagumo = set()
        nagumo_final = []
        for p in raw_nagumo:
            sku = p.get('sku')
            if sku and sku not in vistos_nagumo:
                vistos_nagumo.add(sku)
                nome, desc = p.get('name', ''), p.get('description', '')
                texto_nagumo_norm = remover_acentos(f"{nome} {desc}")
                
                if all(k in texto_nagumo_norm for k in palavras_chave_filtro):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    preco_normal = p.get('price', 0)
                    preco_final = cond[0].get('price') if (promo.get('isActive') and cond) else preco_normal
                    
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
                    
                    label = calcular_preco_unitario_nagumo(preco_final, desc, nome, p.get('unit'))
                    p['unit_label'] = label
                    p['sort_val'] = extrair_valor_unitario(label)
                    p['preco_final'] = preco_final
                    p['preco_normal'] = preco_normal
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'] or 999)

    # --- EXIBIÇÃO COLUNA 1 (SHIBATA) ---
    with col1:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_SHIBATA_URL}" width="80" alt="Shibata" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(shibata_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        if not shibata_final:
            st.warning("Nenhum produto encontrado.")
            
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            descricao = p.get('descricao', '')
            descricao_modificada = descricao
            preco_info_extra = ""
            preco_total = p['preco_final']
            preco_formatado = p['preco_str']

            match = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml)", preco_formatado.lower())
            if match:
                try:
                    q = float(match.group(1).replace(",", "."))
                    u = match.group(2).lower()
                    if u == "g": q /= 1000; u = "kg"
                    elif u == "ml": q /= 1000; u = "l"
                    if q > 0: preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / q:.2f}/{u}</div>"
                except: pass

            if 'papel higienico' in remover_acentos(descricao):
                descricao_modificada = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
                descricao_modificada = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)

            total_folhas, preco_por_folha = calcular_preco_papel_toalha(descricao, preco_total)
            if total_folhas and preco_por_folha:
                descricao_modificada += f" <span style='color:gray;'>({total_folhas} folhas)</span>"
                preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_folha:.3f}/folha</div>"
            else:
                _, preco_por_metro_str = calcular_precos_papel(descricao, preco_total)
                if preco_por_metro_str:
                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_metro_str}</div>"
                elif not re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml|un|l|ml|folhas?|m)", preco_formatado.lower()):
                    _, preco_por_unidade_str = calcular_preco_unidade(descricao, preco_total)
                    if preco_por_unidade_str: preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_unidade_str}</div>"

            if 'ovo' in remover_acentos(descricao).lower():
                match_ovo = re.search(r'(\d+)\s*(unidades|un|ovos|c/|com)', descricao.lower())
                if match_ovo and int(match_ovo.group(1)) > 0:
                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / int(match_ovo.group(1)):.2f}/unidade</div>"
                elif re.search(r'1\s*d[uú]zia', descricao.lower()):
                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / 12:.2f}/unidade (dúzia)</div>"

            oferta = p.get('oferta') or {}
            if p.get('em_oferta') and oferta.get('preco_oferta') and oferta.get('preco_antigo'):
                preco_antigo_val = float(oferta.get('preco_antigo'))
                desconto = round(100 * (preco_antigo_val - float(oferta.get('preco_oferta'))) / preco_antigo_val) if preco_antigo_val else 0
                preco_html = f"<div><b>{preco_formatado}</b><br> <span style='color:red;font-weight: bold;'>({desconto}% OFF)</span></div><div><span style='color:gray; text-decoration: line-through;'>R$ {preco_antigo_val:.2f}</span></div>"
            else:
                preco_html = f"<div><b>{preco_formatado}</b></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{img}' width='80' style='background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;'/>
                        <img src='{LOGO_SHIBATA_URL}' width='80' 
                            style='background-color: white; display: block; margin: 0 auto; border-top: 1.5px solid black; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; padding: 3px;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'><a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{descricao_modificada}</b></a></div>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                        <div style='font-size:0.85em;'>{preco_info_extra}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # --- EXIBIÇÃO COLUNA 2 (NAGUMO) ---
    with col2:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
                <img src="{LOGO_NAGUMO_URL}" width="80" alt="Nagumo" style="margin-right:8px; border-radius: 6px; border: 1.5px solid white; padding: 0px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(nagumo_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        if not nagumo_final:
            st.warning("Nenhum produto encontrado.")
            
        for p in nagumo_final:
            imgs = p.get('photosUrl')
            img = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            titulo = p['name']
            texto_completo = p['name'] + " " + p.get('description', '')
            
            if contem_papel_toalha(texto_completo):
                _, _, _, texto_exibicao = extrair_info_papel_toalha(p['name'], p.get('description', ''))
                if texto_exibicao: titulo += f" <span class='info-cinza'>({texto_exibicao})</span>"
                
            if "papel higi" in remover_acentos(titulo.lower()):
                titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)

            preco_normal = p['preco_normal']
            preco_final = p['preco_final']
            if preco_final < preco_normal:
                desconto_percentual = ((preco_normal - preco_final) / preco_normal) * 100
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_final:.2f}</span><br><span style='color: red; font-weight: bold;'> ({desconto_percentual:.0f}% OFF)</span><br><span style='text-decoration: line-through; color: gray;'>R$ {preco_normal:.2f}</span>"
            else:
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_normal:.2f}</span>"

            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <a href='{p['url_final']}' target='_blank' style='flex: 0 0 auto; text-decoration:none;'>
                        <img src="{img}" width="80" style="background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;"/>
                        <img src="{LOGO_NAGUMO_URL}" width="80" style="border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; border: 1.5px solid white; padding: 0px; display: block;"/>
                    </a>
                    <div style="flex: 1; word-break: break-word; overflow-wrap: anywhere;">
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><strong>{titulo}</strong></a><br>
                        <strong>{preco_html}</strong><br>
                        <div style="margin-top: 4px; font-size: 0.9em; color: #666;">{p['unit_label']}</div>
                        <div style="color: gray; font-size: 0.8em;">Estoque: {p.get('stock', 0)}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(
        f"""
        <script>
            const cols = window.parent.document.querySelectorAll('[data-testid="stColumn"]');
            cols.forEach(col => col.scrollTop = 0);
        </script>
        """,
        height=0, width=0
    )
