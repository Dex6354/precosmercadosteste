import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES ---
API_BASE = "https://api-xsupermercados.applay.tech/api2/ecommerce"
SHOP_SLUG = "xsupermercados"

# Payload de sessão idêntico ao que funcionou no seu log
SESSION_DATA = {
    "session": {
        "loja": {"id": "64b96dd4276891783b1fa25d", "numero": 6},
        "device": {
            "browser": "chrome", 
            "platform": "web", 
            "uuid": "dfdf4d49-0ab9-4aab-ba11-dcbb47ac542d"
        },
        "modality": "Retirada"
    }
}

# --- FUNÇÕES DE EXTRAÇÃO ---

def buscar_x_supermercados(termo):
    """Realiza a autenticação e busca em uma única sessão de rede."""
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "X-Shop-Slug": SHOP_SLUG,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Origin": "https://www.xsupermercados.com.br",
        "Referer": "https://www.xsupermercados.com.br/"
    })

    try:
        # 1. Passo de Autenticação (Session)
        res_auth = s.post(f"{API_BASE}/eauth/session", json=SESSION_DATA, timeout=10)
        if res_auth.status_code != 200:
            return [], f"Erro na Autenticação: {res_auth.status_code}"
        
        token = res_auth.json().get('token')
        if not token:
            return [], "Token não recebido."

        # 2. Atualizar headers com o token recebido
        s.headers.update({
            "Authorization": f"Bearer {token}",
            "X-Session-Token": token
        })

        # 3. Passo de Busca (conforme estrutura do log)
        payload_busca = SESSION_DATA.copy()
        payload_busca.update({
            "filter": {"text": termo},
            "loja_id": 6,
            "pagina": 1,
            "ordenacao": "relevancia"
        })

        res_busca = s.post(f"{API_BASE}/enav/produtos_buscar", json=payload_busca, timeout=15)
        
        if res_busca.status_code == 200:
            return res_busca.json().get('produtos', []), None
        else:
            return [], f"Erro na Busca: {res_busca.status_code} - {res_busca.text[:100]}"

    except Exception as e:
        return [], str(e)

# --- UTILITÁRIOS ---
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '-', text)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="X Supermercados - Poá", layout="wide")

st.markdown("""
    <style>
        .product-card { display: flex; align-items: center; gap: 15px; padding: 10px; border-bottom: 1px solid #eee; }
        .price { color: #2e7d32; font-weight: bold; font-size: 1.1em; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 X Supermercados")
termo_input = st.text_input("Pesquisar produto:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("Sincronizando sessão segura..."):
        produtos_raw, erro = buscar_x_supermercados(termo_input)
        
        if erro:
            st.error(f"Falha técnica: {erro}")
            with st.expander("Ver detalhes do erro"):
                st.write("Verifique se o site oficial está acessível e se os headers de Origin/Referer permanecem os mesmos.")
        else:
            x_final = [p for p in produtos_raw if all(k in remover_acentos(p.get('nome','')) for k in palavras_chave)]
            
            st.write(f"🔎 Encontrados: {len(x_final)}")
            for p in x_final:
                img = p.get('imagem_principal') or "https://via.placeholder.com/80"
                url = f"https://www.xsupermercados.com.br/produto/{p.get('id')}/{slugify(p.get('nome',''))}"
                
                st.markdown(f"""
                    <div class='product-card'>
                        <img src='{img}' width='80'>
                        <div>
                            <a href='{url}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span class='price'>R$ {float(p.get('preco_venda', 0)):.2f}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
