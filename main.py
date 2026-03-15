import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
# Nota: O ORG_ID 131 é referente ao X Supermercados. 
# Se o status da API for 401 ou 403, o TOKEN abaixo expirou.
ORG_ID = "131"
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTMxIn0.y6W8Q-Hn7A9V8_R4X2Q_Z1z7G8"

HEADERS_X = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "domainkey": "www.xsupermercados.com.br",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/"
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

# --- LÓGICA DE EXTRAÇÃO COM DEBUG ---
def buscar_pagina_x(termo, pagina):
    # Rota padrão de busca da VipCommerce
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_X, timeout=15)
        status = r.status_code
        if status == 200:
            return r.json().get('data', {}).get('produtos', []), status, None
        return [], status, r.text
    except Exception as e:
        return [], 0, str(e)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Debug X Supermercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 80vh; padding: 15px; border: 1px solid #f0f2f6; border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("### 🛠 Debugger - X Supermercados")
termo_input = st.text_input("🔎 Pesquisar produto:", "Banana").strip()

if termo_input:
    termos_busca = gerar_formas_variantes(remover_acentos(termo_input))
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("🔍 Consultando API..."):
        raw_x = []
        logs_debug = []
        
        # Busca nas 2 primeiras páginas para os termos variantes
        for t in termos_busca:
            for p_num in range(1, 3):
                produtos, status, erro = buscar_pagina_x(t, p_num)
                logs_debug.append({
                    "termo": t, 
                    "página": p_num, 
                    "status": status, 
                    "itens": len(produtos),
                    "erro": erro[:100] if erro else "OK"
                })
                if produtos:
                    raw_x.extend(produtos)
                else:
                    break # Se a p1 falhar, não tenta a p2

        # --- PAINEL DE DEBUG ---
        with st.expander("🐞 Ver Logs Técnicos (Debugger)"):
            st.write("**Histórico de Requisições:**")
            st.table(logs_debug)
            if raw_x:
                st.write("**Exemplo do primeiro item bruto recebido:**")
                st.json(raw_x[0])
            else:
                st.error("A API não retornou nenhum dado. Verifique se o TOKEN no código ainda é válido.")

        # Processamento e Filtro
        vistos = set()
        x_final = []
        for p in raw_x:
            pid = p.get('id')
            if pid and pid not in vistos and p.get("disponivel", True):
                vistos.add(pid)
                desc = p.get('descricao', '')
                # Filtro rigoroso de palavras-chave
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    preco_final = float(oferta.get('preco_oferta') if (p.get('em_oferta') and oferta.get('preco_oferta')) else p.get('preco', 0))
                    
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    p['preco_final'] = preco_final
                    x_final.append(p)

        x_final = sorted(x_final, key=lambda x: x['preco_final'])

    # --- EXIBIÇÃO ---
    col1, = st.columns([1])
    with col1:
        st.markdown(f"<center><img src='{LOGO_X_URL}' width='150'></center>", unsafe_allow_html=True)
        st.write(f"🔎 {len(x_final)} produtos encontrados (após filtros).")
        
        if not x_final and raw_x:
            st.warning("A API retornou itens, mas nenhum condiz exatamente com as palavras digitadas.")

        for p in x_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image'>
                        <img src='{img}' width='80' style='border-radius:5px; background:white;'/>
                    </a>
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:black;'>
                            <b>{p.get('descricao')}</b>
                        </a><br>
                        <span style='font-size:1.1em; color:green;'><b>R$ {p['preco_final']:.2f}</b></span>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
