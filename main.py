import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES EXTRAÍDAS DO HAR ---
SHOP_SLUG = "xsupermercados"
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "X-Shop-Slug": SHOP_SLUG,
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/",
}

LOGO_X_URL = "https://www.xsupermercados.com.br/assets/images/logo.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES DE API ---

def obter_sessao():
    url = f"{API_BASE}/eauth/session"
    try:
        # Importante: enviar um dicionário vazio {} no json para evitar 401 em alguns endpoints Applay
        r = requests.post(url, headers=HEADERS_BASE, json={}, timeout=10)
        if r.status_code == 200:
            return r.json().get('token'), None
        return None, f"Erro {r.status_code}: {r.text}"
    except Exception as e:
        return None, str(e)

def buscar_produtos_x(termo, token):
    url = f"{API_BASE}/enav/produtos_buscar"
    headers = HEADERS_BASE.copy()
    headers["Authorization"] = f"Bearer {token}"
    
    payload = {
        "termo": termo,
        "loja_id": 1,
        "pagina": 1,
        "ordenacao": "relevancia"
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get('produtos', []), None
        return [], f"Erro {r.status_code}: {r.text}"
    except Exception as e:
        return [], str(e)

# --- UTILITÁRIOS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- INTERFACE ---
st.set_page_config(page_title="X Supermercados", layout="wide")

st.markdown("""
    <style>
        .product-container { display: flex; align-items: center; gap: 10px; padding: 8px; border-bottom: 1px solid #eee; }
        .product-info { flex-grow: 1; }
        .price { color: #2e7d32; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown("### 🛒 X Supermercados")
termo_input = st.text_input("🔎 Pesquisar:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("Autenticando..."):
        token, erro_sessao = obter_sessao()
        
        if token:
            produtos_raw, erro_busca = buscar_produtos_x(termo_input, token)
            
            with st.expander("🐞 Debugger"):
                st.write(f"Token: `{token[:20]}...`")
                if erro_busca: st.error(erro_busca)
                elif produtos_raw: st.write(f"Itens brutos: {len(produtos_raw)}")

            x_final = []
            for p in produtos_raw:
                nome = p.get('nome', '')
                if all(k in remover_acentos(nome) for k in palavras_chave):
                    preco = float(p.get('preco_venda', 0))
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{p.get('id')}/{slugify(nome)}"
                    p['preco_fmt'] = f"R$ {preco:.2f}".replace('.', ',')
                    x_final.append(p)

            st.write(f"🔎 {len(x_final)} produtos encontrados.")

            for p in x_final:
                img = p.get('imagem_principal') or DEFAULT_IMAGE_URL
                st.markdown(f"""
                    <div class='product-container'>
                        <img src='{img}' width='70'/>
                        <div class='product-info'>
                            <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span class='price'>{p['preco_fmt']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.error(f"Falha na autenticação: {erro_sessao}")

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
