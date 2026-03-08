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

# --- LÓGICA DE CÁLCULO (EXTRAÍDA DO MAIN.PY) ---
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

# --- LÓGICA NAGUMO ---
def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_completo = f"{nome} {descricao}".lower()
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        rolos, folhas = int(match.group(1)), int(match.group(3))
        return rolos, folhas, rolos * folhas, f"{rolos} un, {folhas} folhas"
    return None, None, None, None

def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    texto_completo = f"{nome} {descricao}".lower()
    if contem_papel_toalha(texto_completo):
        _, _, total_folhas, _ = extrair_info_papel_toalha(nome, descricao)
        if total_folhas: return f"R$ {preco_valor / total_folhas:.3f}".replace('.', ',') + "/folha"
    
    if "papel higi" in texto_completo:
        m_rolos = re.search(r"(\d+)\s*(rolos?|un|unidades?)", texto_completo)
        m_metros = re.search(r"(\d+[.,]?\d*)\s*(m|metros?|mt)", texto_completo)
        if m_rolos and m_metros:
            try:
                rolos = int(m_rolos.group(1))
                metros = float(m_metros.group(1).replace(',', '.'))
                return f"R$ {preco_valor / (rolos * metros):.3f}".replace('.', ',') + "/m"
            except: pass

    # Genérico (kg, L, un)
    res_v, res_s = calcular_preco_unidade(texto_completo, preco_valor)
    if res_s: return res_s
    return f"R$ {preco_valor:.2f}".replace('.', ',') + "/un"

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
    palavras_chave = remover_acentos(termo).split()

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
            if pid and pid not in vistos_shibata:
                vistos_shibata.add(pid)
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['preco_final'] = preco_final
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    
                    # Cálculo de Unidade e Ordenação Corrigida (usando fracionamento da API)
                    val_metro, _ = calcular_precos_papel(desc, preco_final)
                    _, val_folha = calcular_preco_papel_toalha(desc, preco_final)
                    val_unidade, _ = calcular_preco_unidade(desc, preco_final)
                    
                    if 'papel toalha' in remover_acentos(termo) and val_folha: 
                        p['sort_val'] = val_folha
                    elif 'papel higienico' in remover_acentos(termo) and val_metro: 
                        p['sort_val'] = val_metro
                    else: 
                        if val_unidade:
                            p['sort_val'] = val_unidade
                        else:
                            # Tenta puxar a unidade e passo direto da API do Shibata (ex: maçã 1 Unidade, passo 0.2kg)
                            passo_raw = str(p.get('passo') or '1').replace(',', '.')
                            try:
                                passo_api = float(passo_raw)
                            except:
                                passo_api = 1.0
                                
                            unidade_api = str(p.get('unidade') or '').lower()
                            
                            if unidade_api == 'kg' and passo_api > 0:
                                p['sort_val'] = preco_final / passo_api
                            elif unidade_api in ['g', 'grama', 'gramas'] and passo_api > 0:
                                p['sort_val'] = preco_final / (passo_api / 1000)
                            elif unidade_api in ['l', 'litro', 'litros'] and passo_api > 0:
                                p['sort_val'] = preco_final / passo_api
                            elif unidade_api in ['ml', 'mililitro', 'mililitros'] and passo_api > 0:
                                p['sort_val'] = preco_final / (passo_api / 1000)
                            else:
                                p['sort_val'] = preco_final
                    
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
                if all(k in remover_acentos(f"{nome} {desc}") for k in palavras_chave):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    preco_normal = p.get('price', 0)
                    preco_final = cond[0].get('price') if (promo.get('isActive') and cond) else preco_normal
                    
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
                    label = calcular_preco_unitario_nagumo(preco_final, desc, nome)
                    p['unit_label'] = label
                    p['sort_val'] = extrair_valor_unitario(label)
                    p['preco_final'] = preco_final
                    p['preco_normal'] = preco_normal
                    nagumo_final.append(p)
        nagumo_final = sorted(nagumo_final, key=lambda x: x['sort_val'] or 999)

    # --- EXIBIÇÃO COLUNA 1 (SHIBATA) ---
    with col1:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_SHIBATA_URL}' width='80'/></h5>", unsafe_allow_html=True)
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            desc = p['descricao']
            preco_total = p['preco_final']
            preco_info_extra = ""
            
            # Formatação Desconto (Layout Original Mantido e Protegido)
            preco_total_str = f"{preco_total:.2f}".replace('.', ',')
            oferta = p.get('oferta') or {}
            
            if p.get('em_oferta') and oferta.get('preco_antigo'):
                p_antigo = float(oferta.get('preco_antigo'))
                desc_perc = round(100 * (p_antigo - preco_total) / p_antigo)
                p_antigo_str = f"{p_antigo:.2f}".replace('.', ',')
                preco_html = f"<div><b>R$ {preco_total_str}</b> <span style='color:red;'>({desc_perc}% OFF)</span></div><div style='text-decoration:line-through; color:gray;'>R$ {p_antigo_str}</div>"
            else:
                preco_html = f"<div><b>R$ {preco_total_str}</b></div>"

            # Info extra (Papel, Ovos, kg, un, etc)
            if 'papel higienico' in remover_acentos(desc):
                desc = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", desc, flags=re.IGNORECASE)
                desc = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", desc, flags=re.IGNORECASE)
                _, p_metro = calcular_precos_papel(desc, preco_total)
                if p_metro: preco_info_extra = f"<div style='color:gray;'>{p_metro}</div>"
            
            total_folhas, p_folha = calcular_preco_papel_toalha(desc, preco_total)
            if p_folha: 
                preco_info_extra = f"<div style='color:gray;'>R$ {f'{p_folha:.3f}'.replace('.', ',')}/folha</div>"
            elif not preco_info_extra:
                _, p_un = calcular_preco_unidade(desc, preco_total)
                if p_un: 
                    preco_info_extra = f"<div style='color:gray;'>{p_un}</div>"
                else:
                    # Faz o cálculo correto dividindo pelo fracionamento ("passo") reportado pela API
                    passo_raw = str(p.get('passo') or '1').replace(',', '.')
                    try:
                        passo_api = float(passo_raw)
                    except:
                        passo_api = 1.0
                        
                    unidade_api = str(p.get('unidade') or '').lower()
                    
                    if unidade_api == 'kg' and passo_api > 0:
                        preco_kg = preco_total / passo_api
                        preco_info_extra = f"<div style='color:gray;'>R$ {f'{preco_kg:.2f}'.replace('.', ',')}/kg</div>"
                    elif unidade_api in ['g', 'grama', 'gramas'] and passo_api > 0:
                        preco_kg = preco_total / (passo_api / 1000)
                        preco_info_extra = f"<div style='color:gray;'>R$ {f'{preco_kg:.2f}'.replace('.', ',')}/kg</div>"
                    elif unidade_api in ['l', 'litro', 'litros'] and passo_api > 0:
                        preco_l = preco_total / passo_api
                        preco_info_extra = f"<div style='color:gray;'>R$ {f'{preco_l:.2f}'.replace('.', ',')}/L</div>"
                    elif unidade_api in ['ml', 'mililitro', 'mililitros'] and passo_api > 0:
                        preco_l = preco_total / (passo_api / 1000)
                        preco_info_extra = f"<div style='color:gray;'>R$ {f'{preco_l:.2f}'.replace('.', ',')}/L</div>"
                    else:
                        preco_info_extra = f"<div style='color:gray;'>R$ {preco_total_str}/un</div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'><img src='{img}' width='80'/></a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{desc}</b></a>
                        {preco_html}
                        {preco_info_extra}
                    </div>
                </div><hr class='product-separator'/>
            """, unsafe_allow_html=True)

    # --- EXIBIÇÃO COLUNA 2 (NAGUMO) ---
    with col2:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_NAGUMO_URL}' width='80'/></h5>", unsafe_allow_html=True)
        for p in nagumo_final:
            img = p.get('photosUrl')[0] if p.get('photosUrl') else DEFAULT_IMAGE_URL
            titulo = p['name']
            
            # Estilo Papel
            if "papel higi" in remover_acentos(titulo):
                titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)

            # Preço e Promoção (Layout Original Mantido e Protegido)
            preco_final_str = f"{p['preco_final']:.2f}".replace('.', ',')
            
            if p['preco_final'] < p['preco_normal']:
                preco_normal_str = f"{p['preco_normal']:.2f}".replace('.', ',')
                desc_perc = ((p['preco_normal'] - p['preco_final']) / p['preco_normal']) * 100
                preco_html = f"<b>R$ {preco_final_str}</b> <span style='color:red;'>({desc_perc:.0f}% OFF)</span><br><span style='text-decoration:line-through; color:gray;'>R$ {preco_normal_str}</span>"
            else:
                preco_html = f"<b>R$ {preco_final_str}</b>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'><img src='{img}' width='80'/></a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{titulo}</b></a><br>
                        {preco_html}<br>
                        <div style='color:gray;'>{p['unit_label']}</div>
                    </div>
                </div><hr class='product-separator'/>
            """, unsafe_allow_html=True)

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
