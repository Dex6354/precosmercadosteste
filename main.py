import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time

# --- CONFIGURAÇÕES E CONSTANTES ---
# No sistema Applay, o identificador principal é o slug da loja
SHOP_SLUG = "xsupermercados"
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"

HEADERS_X = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Shop-Slug": SHOP_SLUG,
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/"
}

LOGO_X_URL = "https://www.xsupermercados.com.br/assets/images/logo.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES UTILITÁRIAS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- LÓGICA DE EXTRAÇÃO ---
def buscar_produtos_x(termo):
    url = f"{API_BASE}/enav/produtos_buscar"
    # O payload segue o padrão da API Applay observado no tráfego
    payload = {
        "termo": termo,
        "loja_id": 1,
        "pagina": 1,
        "ordenacao": "relevancia"
    }
    
    try:
        r = requests.post(url, headers=HEADERS_X, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # A Applay costuma retornar os produtos dentro de 'data' ou 'produtos'
            return data.get('produtos', []), r.status_code, None
        return [], r.status_code, r.text
    except Exception as e:
        return [], 0, str(e)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="X Supermercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] { overflow-y: auto; max-height: 80vh; padding: 15px; border: 1px solid #f0f2f6; border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

st.markdown("### 🛒 X Supermercados")
termo_input = st.text_input("🔎 Pesquisar produto:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("🔍 Consultando X Supermercados..."):
        produtos_raw, status, erro = buscar_produtos_x(termo_input)
        
        # --- DEBUG ---
        with st.expander("🐞 Debugger"):
            st.write(f"Status: {status}")
            if erro: st.error(f"Erro: {erro}")
            if produtos_raw: st.json(produtos_raw[0])

        x_final = []
        for p in produtos_raw:
            # No Applay, os campos costumam ser: nome, preco_venda, imagem_principal
            nome = p.get('nome', '')
            if all(k in remover_acentos(nome) for k in palavras_chave):
                # Alguns itens vêm com preço em centavos ou string, tratamos aqui
                preco = float(p.get('preco_venda', 0))
                
                # Gerar URL do produto
                id_prod = p.get('id')
                p['url_final'] = f"https://www.xsupermercados.com.br/produto/{id_prod}/{slugify(nome)}"
                p['preco_fmt'] = f"R$ {preco:.2f}".replace('.', ',')
                p['nome_limpo'] = nome
                x_final.append(p)

    # --- EXIBIÇÃO ---
    col1, = st.columns([1])
    with col1:
        st.markdown(f"<center><img src='{LOGO_X_URL}' width='150'></center>", unsafe_allow_html=True)
        st.write(f"🔎 {len(x_final)} produtos encontrados.")
        
        for p in x_final:
            img = p.get('imagem_principal') or DEFAULT_IMAGE_URL
            
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:5px; background:white;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'>
                            <b>{p['nome_limpo']}</b>
                        </a><br>
                        <span style='font-size:1.1em; color:green;'><b>{p['preco_fmt']}</b></span>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
