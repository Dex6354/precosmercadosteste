import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"
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

# --- LÓGICA DE CÁLCULO ---
def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    # KG
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    # Gramas
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}/kg"
    # Litros
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"
    # ML
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}/L"
    return None, None

# --- REQUISIÇÃO ATACADÃO ---
def buscar_atacadao(termo, pagina=0):
    # O Atacadão utiliza uma API de busca VTEX/Intelligent Search
    url = f"https://www.atacadao.com.br/api/v1/search?q={termo}&page={pagina + 1}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json().get('products', [])
    except:
        pass
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Atacadão", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div, span, strong, small { font-size: 0.85rem !important; }
        .product-container { 
            display: flex; align-items: center; gap: 15px; 
            padding: 10px; border: 1px solid #eee; border-radius: 8px; margin-bottom: 10px;
        }
        .product-image-container { min-width: 100px; text-align: center; }
        .product-info { flex: 1; }
        .price-main { font-size: 1.1rem !important; color: #d32f2f; font-weight: bold; }
        .price-unit { color: #666; font-size: 0.8rem !important; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛒 Comparador Atacadão</h3>", unsafe_allow_html=True)
termo_busca = st.text_input("🔎 Digite o produto:", "Arroz").strip()

if termo_busca:
    palavras_chave = remover_acentos(termo_busca).split()
    
    with st.spinner("🔍 Consultando Atacadão..."):
        raw_results = []
        # Busca variações para maior abrangência
        termos = gerar_formas_variantes(remover_acentos(termo_busca))
        
        with ThreadPoolExecutor(max_workers=5) as exe:
            futures = [exe.submit(buscar_atacadao, t, 0) for t in termos]
            for f in as_completed(futures):
                raw_results.extend(f.result())

        # Processamento e Filtro
        vistos = set()
        final_list = []
        for p in raw_results:
            sku = p.get('productId')
            if sku and sku not in vistos:
                vistos.add(sku)
                nome = p.get('productName', '')
                
                # Validação de palavras-chave
                if all(k in remover_acentos(nome) for k in palavras_chave):
                    # Extração de Preço (considerando o primeiro item do array de preços)
                    try:
                        sellers = p.get('items', [{}])[0].get('sellers', [{}])[0]
                        comm = sellers.get('commertialOffer', {})
                        preco_final = comm.get('Price', 0)
                        link = p.get('link', '')
                        img = p.get('items', [{}])[0].get('images', [{}])[0].get('imageUrl', DEFAULT_IMAGE_URL)
                        
                        calc_val, calc_label = calcular_preco_unidade(nome, preco_final)
                        
                        final_list.append({
                            'nome': nome,
                            'preco': preco_final,
                            'link': f"https://www.atacadao.com.br{link}",
                            'img': img,
                            'unit_label': calc_label,
                            'sort_val': calc_val or preco_final
                        })
                    except:
                        continue

        # Ordenação por preço unitário (ou total se não houver unidade)
        final_list = sorted(final_list, key=lambda x: x['sort_val'])

        st.write(f"Encontrados {len(final_list)} produtos.")

        # Exibição em Grid
        for item in final_list:
            st.markdown(f"""
                <div class='product-container'>
                    <div class='product-image-container'>
                        <a href='{item['link']}' target='_blank'>
                            <img src='{item['img']}' width='90' style='border-radius:5px;'/>
                        </a>
                    </div>
                    <div class='product-info'>
                        <a href='{item['link']}' target='_blank' style='text-decoration:none; color:#333;'>
                            <strong>{item['nome']}</strong>
                        </a>
                        <div class='price-main'>R$ {item['preco']:.2f}</div>
                        <div class='price-unit'>{item['unit_label'] if item['unit_label'] else ""}</div>
                    </div>
                    <div style='min-width:100px; text-align:right;'>
                        <img src='{LOGO_ATACADAO_URL}' width='60'/>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    # Scroll to top script
    components.html(
        f"<script>window.parent.document.querySelector('.main').scrollTop = 0;</script>",
        height=0
    )
