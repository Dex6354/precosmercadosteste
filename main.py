import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"
SHOP_SLUG = "xsupermercados"

HEADERS_BASE = {
    "Content-Type": "application/json",
    "X-Shop-Slug": SHOP_SLUG,
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/"
}

# --- FUNÇÕES DE API ---

def iniciar_sessao():
    """Simula a inicialização da sessão conforme o HAR fornecido."""
    url = f"{API_BASE}/eauth/session"
    # Payload extraído do seu JSON de sessão
    payload = {
        "session": {
            "loja": {"id": "64b96dd4276891783b1fa25d", "numero": 6},
            "device": {"browser": "chrome", "platform": "web"},
            "modality": "Retirada"
        }
    }
    try:
        r = requests.post(url, headers=HEADERS_BASE, json=payload, timeout=10)
        if r.status_code == 200:
            return r.json().get('token'), None
        return None, f"Erro Sessão {r.status_code}: {r.text}"
    except Exception as e:
        return None, str(e)

def buscar_produtos_x(termo, token):
    """Busca os produtos usando o token de sessão."""
    url = f"{API_BASE}/enav/produtos_buscar"
    headers = HEADERS_BASE.copy()
    headers["Authorization"] = f"Bearer {token}"
    headers["X-Session-Token"] = token
    
    payload = {
        "termo": termo,
        "loja_id": 6,  # ID da loja de Poá conforme o HAR
        "pagina": 1,
        "ordenacao": "relevancia"
    }
    
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            return r.json().get('produtos', []), None
        return [], f"Erro Busca {r.status_code}"
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
        .product-card { display: flex; align-items: center; gap: 12px; padding: 10px; border-bottom: 1px solid #eee; }
        .price { color: #2e7d32; font-weight: bold; font-size: 1.1em; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 X Supermercados - Poá")
termo_input = st.text_input("O que você procura?", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("Buscando ofertas..."):
        token, erro_s = iniciar_sessao()
        
        if token:
            produtos_raw, erro_b = buscar_produtos_x(termo_input, token)
            
            with st.expander("🐞 Logs de Sistema"):
                st.write(f"Token Ativo: `{token[:25]}...` (Loja 6)")
                if erro_b: st.error(erro_b)

            x_final = []
            for p in produtos_raw:
                nome = p.get('nome', '')
                if all(k in remover_acentos(nome) for k in palavras_chave):
                    preco = float(p.get('preco_venda', 0))
                    p['url_link'] = f"https://www.xsupermercados.com.br/produto/{p.get('id')}/{slugify(nome)}"
                    p['preco_fmt'] = f"R$ {preco:.2f}".replace('.', ',')
                    x_final.append(p)

            st.write(f"Encontrados: {len(x_final)}")
            for p in x_final:
                img = p.get('imagem_principal') or "https://via.placeholder.com/80"
                st.markdown(f"""
                    <div class='product-card'>
                        <img src='{img}' width='80'>
                        <div>
                            <a href='{p['url_link']}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span class='price'>{p['preco_fmt']}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.error(f"Erro na Sessão: {erro_s}")

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
