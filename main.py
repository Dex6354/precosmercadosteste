import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
import json
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
REGION_ID_BASE64 = "U1cjYXRhY2FkYW9icjY1Ng=="
SELLER_ID = "atacadaobr656"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Função para carregar a logo local e converter para base64
def get_base64_logo(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
        return f"data:image/png;base64,{base64.b64encode(data).decode()}"
    except:
        return ""

LOGO_ATACADAO_B64 = get_base64_logo("logo-atacadao.png")

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
    # ML
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    # Unidades
    match_un = re.search(r'(\d+)\s*(unidades|un|ovos|c/|com)', desc_minus)
    if match_un and int(match_un.group(1)) > 0:
        qtd = int(match_un.group(1))
        return preco_total / qtd, f"R$ {preco_total / qtd:.2f}".replace('.', ',') + "/un"
    return None, None

# --- REQUISIÇÃO ATACADÃO ---
def buscar_atacadao(termo):
    url = "https://www.atacadao.com.br/api/graphql?operationName=ProductsQuery"
    payload = {
        "operationName": "ProductsQuery",
        "variables": {
            "first": 50, "after": "0", "sort": "score_desc", "term": termo,
            "selectedFacets": [
                {"key": "region-id", "value": REGION_ID_BASE64},
                {"key": "channel", "value": json.dumps({"salesChannel": "1", "seller": SELLER_ID, "regionId": REGION_ID_BASE64})},
                {"key": "locale", "value": "pt-BR"}
            ]
        }
    }
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json().get('data', {}).get('search', {}).get('products', {}).get('edges', [])
    except: pass
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Atacadão", page_icon="🛒", layout="wide")

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
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Atacadão</h6>", unsafe_allow_html=True)
termo_input = st.text_input("🔎 Digite o nome do produto:", "Arroz").strip()

if termo_input:
    termos_busca = gerar_formas_variantes(remover_acentos(termo_input))
    palavras_chave = remover_acentos(termo_input).split()

    with st.spinner("🔍 Buscando no Atacadão..."):
        raw_results = []
        for t in termos_busca: raw_results.extend(buscar_atacadao(t))
        
        vistos = set()
        atacadao_final = []
        for edge in raw_results:
            node = edge.get('node', {})
            pid, nome = node.get('id'), node.get('name', '')
            if pid and pid not in vistos and all(k in remover_acentos(nome) for k in palavras_chave):
                vistos.add(pid)
                offers = node.get('offers', {}).get('offers', [])
                preco_varejo = offers[0].get('price', 0) if offers else 0
                preco_atacado = offers[1].get('price', 0) if len(offers) > 1 else None
                val_unit, label_unit = calcular_preco_unidade(nome, preco_varejo)
                
                atacadao_final.append({
                    'nome': nome, 'preco': preco_varejo, 'preco_atacado': preco_atacado,
                    'url': f"https://www.atacadao.com.br{node.get('slug')}/p",
                    'img': node.get('image', [{}])[0].get('url', DEFAULT_IMAGE_URL),
                    'label_unit': label_unit, 'sort_val': val_unit or preco_varejo
                })
        atacadao_final = sorted(atacadao_final, key=lambda x: x['sort_val'] or 999)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_ATACADAO_B64}" width="100" alt="Atacadão" style="background-color: white; border-radius: 4px; padding: 5px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(atacadao_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)

        for p in atacadao_final:
            preco_html = f"<div><b>R$ {p['preco']:.2f}</b>".replace('.', ',') + "</div>"
            if p['preco_atacado']:
                preco_html += f"<div style='color:green; font-size:0.7em;'>Atacado: R$ {p['preco_atacado']:.2f}</div>".replace('.', ',')
            
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url']}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{p['img']}' width='80' style='background-color: white; border-radius: 6px; display: block; border: 1px solid #eee;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'><a href='{p['url']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{p['nome']}</b></a></div>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                        <div style='font-size:0.85em; color:gray;'>{p['label_unit'] if p['label_unit'] else ''}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(f"<script>const cols = window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]'); cols.forEach(col => col.scrollTop = 0);</script>", height=0)
