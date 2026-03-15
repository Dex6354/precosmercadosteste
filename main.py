import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
SHOP_SLUG = "xsupermercados"
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"

# Cabeçalhos base
HEADERS_BASE = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Shop-Slug": SHOP_SLUG,
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/"
}

LOGO_X_URL = "https://www.xsupermercados.com.br/assets/images/logo.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES DE API ---

def obter_sessao():
    """Gera um token de sessão dinâmico para evitar o erro 401."""
    url = f"{API_BASE}/eauth/session"
    try:
        # Payload vazio conforme padrão Applay para novas sessões
        r = requests.post(url, headers=HEADERS_BASE, json={}, timeout=10)
        if r.status_code == 200:
            return r.json().get('token'), None
        return None, f"Erro Sessão: {r.status_code}"
    except Exception as e:
        return None, str(e)

def buscar_produtos_x(termo, token):
    """Realiza a busca utilizando o token obtido."""
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
            return r.json().get('produtos', []), r.status_code, None
        return [], r.status_code, r.text
    except Exception as e:
        return [], 0, str(e)

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
        .product-container { display: flex; align-items: center; gap: 10px; padding: 10px; }
        .product-image { min-width: 80px; max-width: 80px; }
        hr { margin: 5px 0; border: 0; border-top: 1px solid #eee; }
    </style>
""", unsafe_allow_html=True)

st.markdown("### 🛒 X Supermercados")
termo_input = st.text_input("🔎 Pesquisar:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("🔐 Autenticando e Buscando..."):
        # 1. Obter Token
        token, erro_sessao = obter_sessao()
        
        if token:
            # 2. Buscar Produtos
            produtos_raw, status, erro_busca = buscar_produtos_x(termo_input, token)
            
            # Debugger
            with st.expander("🐞 Debugger"):
                st.write(f"Token Gerado: `{token[:20]}...`")
                st.write(f"Status Busca: {status}")
                if erro_busca: st.error(erro_busca)

            x_final = []
            for p in produtos_raw:
                nome = p.get('nome', '')
                if all(k in remover_acentos(nome) for k in palavras_chave):
                    preco = float(p.get('preco_venda', 0))
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{p.get('id')}/{slugify(nome)}"
                    p['preco_fmt'] = f"R$ {preco:.2f}".replace('.', ',')
                    x_final.append(p)

            # Exibição
            st.markdown(f"<center><img src='{LOGO_X_URL}' width='150'></center>", unsafe_allow_html=True)
            st.write(f"🔎 {len(x_final)} produtos encontrados.")

            for p in x_final:
                img = p.get('imagem_principal') or DEFAULT_IMAGE_URL
                st.markdown(f"""
                    <div class='product-container'>
                        <a href='{p['url_final']}' target='_blank' class='product-image'>
                            <img src='{img}' width='80'/>
                        </a>
                        <div>
                            <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span style='color:green;'><b>{p['preco_fmt']}</b></span>
                        </div>
                    </div>
                    <hr>
                """, unsafe_allow_html=True)
        else:
            st.error(f"Falha na autenticação: {erro_sessao}")

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
