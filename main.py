import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
ORG_ID = "131"  # ID específico do X Supermercados
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTMxIn0.y6W8Q-Hn7A9V8_R4X2Q_Z1z7G8" # Token atualizado para Org 131

HEADERS_X = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "domainkey": "www.xsupermercados.com.br",
    "User-Agent": "Mozilla/5.0"
}

LOGO_X_URL = "https://www.xsupermercados.com.br/assets/images/logo.png"
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

def formatar_preco_x(preco_total, qtd, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

# --- REQUISIÇÕES ---
def buscar_pagina_x(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_X, timeout=10)
        if r.status_code == 200: return r.json().get('data', {}).get('produtos', [])
    except: pass
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços X Supermercados", page_icon="🛒", layout="wide")

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

st.markdown("<h6>🛒 Preços Mercados - X Supermercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, = st.columns([1])
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando no X Supermercados..."):
        raw_x = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_x, t, p) for t in termos_busca for p in range(1, 4)]
            for f in as_completed(fs): raw_x.extend(f.result())
        
        vistos_x = set()
        x_final = []
        for p in raw_x:
            pid = p.get('id')
            if pid and pid not in vistos_x and p.get("disponivel", True):
                vistos_x.add(pid)
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    p['preco_str'] = formatar_preco_x(preco_final, p.get('quantidade_unidade_diferente'), p.get('unidade_sigla'))
                    p['preco_final'] = preco_final
                    x_final.append(p)
        
        x_final = sorted(x_final, key=lambda x: x['preco_final'])

    with col1:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_X_URL}" width="120" alt="X Supermercados" style="background-color: white; border-radius: 4px; padding: 5px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(x_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        for p in x_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            
            oferta = p.get('oferta') or {}
            if p.get('em_oferta') and oferta.get('preco_antigo'):
                preco_antigo = float(oferta.get('preco_antigo'))
                desconto = round(100 * (preco_antigo - p['preco_final']) / preco_antigo) if preco_antigo else 0
                preco_html = f"<div><b>{p['preco_str']}</b> <span style='color:red; font-weight:bold;'>({desconto}% OFF)</span></div>"
                preco_html += f"<div><span style='color:gray; text-decoration:line-through;'>R$ {preco_antigo:.2f}</span></div>"
            else:
                preco_html = f"<div><b>{p['preco_str']}</b></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{img}' width='80' style='background-color: white; border-radius: 6px; display: block;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'><a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{p.get('descricao')}</b></a></div>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(f"<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
