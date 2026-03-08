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
    # Remove acentos do termo de busca para garantir a requisição correta
    termo_limpo = remover_acentos(termo)
    variantes = {termo_limpo}
    if termo_limpo.endswith("s"): variantes.add(termo_limpo[:-1])
    else: variantes.add(termo_limpo + "s")
    return list(variantes)

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- LÓGICA DE CÁLCULO (ITEM DO CÓDIGO ANTIGO) ---
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
    # Busca KG ou Quilo
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    # Busca Gramas
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
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
termo_input = st.text_input("🔎 Digite o nome do produto:", "Maca Gala").strip()

if termo_input:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(termo_input)
    palavras_filtro = remover_acentos(termo_input).split()

    with st.spinner("🔍 Buscando..."):
        # --- SHIBATA ---
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 4)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        vistos_shibata = set()
        shibata_final = []
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_shibata:
                vistos_shibata.add(pid)
                desc_p = p.get('descricao', '')
                desc_limpa = remover_acentos(desc_p)
                
                # Lógica de filtro corrigida para retornar todos os itens (como as 4 maçãs)
                if all(palavra in desc_limpa for palavra in palavras_filtro):
                    oferta = p.get('oferta') or {}
                    p_oferta = oferta.get('preco_oferta') if isinstance(oferta, dict) else None
                    p_base = p.get('preco') or 0
                    preco_final = float(p_oferta) if (p.get('em_oferta') and p_oferta) else float(p_base)
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc_p)}"
                    p['preco_str'] = formatar_preco_shibata(preco_final, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['preco_val'] = preco_final
                    
                    # Cálculo para Ordenação
                    val_u, _ = calcular_preco_unidade(desc_p, preco_final)
                    val_m, _ = calcular_precos_papel(desc_p, preco_final)
                    p['sort_val'] = val_u or val_m or preco_final
                    
                    shibata_final.append(p)
        
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'])

    # --- COLUNA 1: SHIBATA ---
    with col1:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_SHIBATA_URL}' width='80' style='background:white; padding:3px; border-radius:4px;'/></h5>", unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(shibata_final)} itens encontrados</small>", unsafe_allow_html=True)
        
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            desc = p['descricao']
            desc_layout = desc
            
            # Cores para Papel Higiênico (Lógica antiga)
            if 'papel higienico' in remover_acentos(desc):
                desc_layout = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", desc_layout, flags=re.IGNORECASE)
                desc_layout = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", desc_layout, flags=re.IGNORECASE)
            
            # Cálculos de Unidade/Metro
            info_extra = ""
            _, unit_str = calcular_preco_unidade(desc, p['preco_val'])
            if unit_str: info_extra = f"<div style='color:gray;'>{unit_str}</div>"
            else:
                _, metro_str = calcular_precos_papel(desc, p['preco_val'])
                if metro_str: info_extra = f"<div style='color:gray;'>{metro_str}</div>"

            # Layout de Preço/Desconto
            oferta = p.get('oferta') or {}
            if p.get('em_oferta') and isinstance(oferta, dict) and oferta.get('preco_antigo'):
                p_de = float(oferta.get('preco_antigo'))
                off = round(100 * (p_de - p['preco_val']) / p_de)
                preco_html = f"<b>{p['preco_str']}</b> <span style='color:red;'>({off}% OFF)</span><br><span style='text-decoration:line-through; color:gray;'>R$ {p_de:.2f}</span>"
            else:
                preco_html = f"<b>{p['preco_str']}</b>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='background:white; border-radius:6px 6px 0 0;'/>
                        <img src='{LOGO_SHIBATA_URL}' width='80' style='background:white; border-top:1.5px solid black; padding:2px;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{desc_layout}</b></a>
                        <div style='margin-top:4px;'>{preco_html}</div>
                        {info_extra}
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    with col2:
        st.info("Resultados do Nagumo seriam exibidos aqui com lógica similar.")

    components.html("<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
