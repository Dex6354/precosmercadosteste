import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES EXTRAÍDAS DO HAR ---
SHOP_SLUG = "xsupermercados"
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"

# Cabeçalhos obrigatórios identificados no tráfego da rede
HEADERS_BASE = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "X-Shop-Slug": SHOP_SLUG,
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/",
    "Sec-GPC": "1"
}

LOGO_X_URL = "https://www.xsupermercados.com.br/assets/images/logo.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# --- FUNÇÕES DE API ---

def obter_sessao():
    """Gera um token de sessão dinâmico via endpoint eauth/session."""
    url = f"{API_BASE}/eauth/session"
    try:
        # A API Applay exige um POST mesmo para gerar a sessão inicial
        r = requests.post(url, headers=HEADERS_BASE, json={}, timeout=10)
        if r.status_code == 200:
            return r.json().get('token'), None
        return None, f"Erro Sessão: {r.status_code} - {r.text}"
    except Exception as e:
        return None, str(e)

def buscar_produtos_x(termo, token):
    """Realiza a busca de produtos utilizando o Bearer Token."""
    url = f"{API_BASE}/enav/produtos_buscar"
    headers = HEADERS_BASE.copy()
    headers["Authorization"] = f"Bearer {token}"
    
    # Parâmetros padrão de busca do X Supermercados
    payload = {
        "termo": termo,
        "loja_id": 1,
        "pagina": 1,
        "ordenacao": "relevancia"
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            # A API retorna os produtos em uma lista dentro da chave 'produtos'
            return data.get('produtos', []), r.status_code, None
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
        .product-container { display: flex; align-items: center; gap: 15px; padding: 10px; border-bottom: 1px solid #eee; }
        .product-image { min-width: 80px; max-width: 80px; height: 80px; object-fit: contain; }
        .price-tag { color: #2e7d32; font-weight: bold; font-size: 1.1em; }
    </style>
""", unsafe_allow_html=True)

st.markdown("### 🛒 X Supermercados")
termo_input = st.text_input("🔎 Pesquisar:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("Conectando ao X Supermercados..."):
        token, erro_sessao = obter_sessao()
        
        if token:
            produtos_raw, status, erro_busca = buscar_produtos_x(termo_input, token)
            
            with st.expander("🐞 Debug Técnico"):
                st.code(f"Token: {token[:30]}...")
                st.write(f"Status API: {status}")
                if erro_busca: st.error(erro_busca)

            x_final = []
            for p in produtos_raw:
                nome = p.get('nome', '')
                if all(k in remover_acentos(nome) for k in palavras_chave):
                    preco = float(p.get('preco_venda', 0))
                    # Construção da URL do produto baseada no padrão do site
                    id_prod = p.get('id')
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{id_prod}/{slugify(nome)}"
                    p['preco_fmt'] = f"R$ {preco:.2f}".replace('.', ',')
                    x_final.append(p)

            st.write(f"🔎 {len(x_final)} produtos encontrados.")

            for p in x_final:
                img = p.get('imagem_principal') or DEFAULT_IMAGE_URL
                st.markdown(f"""
                    <div class='product-container'>
                        <a href='{p['url_final']}' target='_blank'>
                            <img src='{img}' class='product-image'/>
                        </a>
                        <div>
                            <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span class='price-tag'>{p['preco_fmt']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.error(f"Falha na autenticação: {erro_sessao}")

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
