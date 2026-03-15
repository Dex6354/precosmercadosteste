import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
ORG_ID = "131" 
# Nota: Tokens de APIs baseadas em JWT expiram. Se parar de funcionar, o token precisa ser renovado.
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTMxIn0.y6W8Q-Hn7A9V8_R4X2Q_Z1z7G8"

HEADERS_X = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "domainkey": "www.xsupermercados.com.br",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
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

# --- REQUISIÇÕES COM DEBUG ---
def buscar_pagina_x(termo, pagina):
    # Endpoint padrão da VipCommerce para o X
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_X, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return data.get('data', {}).get('produtos', []), r.status_code, None
        return [], r.status_code, r.text
    except Exception as e:
        return [], 0, str(e)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Debug X Supermercados", page_icon="🛒", layout="wide")

# CSS omitido para brevidade (mantido igual ao original)
st.markdown("<style>.product-container { display: flex; align-items: center; gap: 10px; } .product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }</style>", unsafe_allow_html=True)

st.markdown("### 🛠 Debugger: X Supermercados")
termo = st.text_input("🔎 Digite o produto:", "Banana").strip()

if termo:
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()
    
    with st.spinner("🔍 Consultando API..."):
        raw_x = []
        debug_info = []
        
        # Busca sequencial simples para facilitar o debug (pode voltar para ThreadPool depois)
        for t in termos_busca:
            produtos, status, erro = buscar_pagina_x(t, 1)
            debug_info.append({"termo": t, "status": status, "qtd_retornada": len(produtos), "erro_bruto": erro[:200] if erro else "Nenhum"})
            raw_x.extend(produtos)

        # Exibe Painel de Debugger
        with st.expander("🐞 Visualizar Logs da API"):
            st.write(debug_info)
            if raw_x:
                st.write("Exemplo do 1º item retornado:", raw_x[0])

        # Processamento e Filtro
        vistos_x = set()
        x_final = []
        for p in raw_x:
            pid = p.get('id')
            if pid and pid not in vistos_x:
                vistos_x.add(pid)
                desc = p.get('descricao', '')
                # Se o filtro de palavras-chave estiver matando os resultados, avisamos aqui
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['url_final'] = f"https://www.xsupermercados.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    p['preco_final'] = preco_final
                    x_final.append(p)

        if not x_final:
            st.error("Nenhum item passou pelos filtros de busca. Verifique se as palavras-chave coincidem com a descrição da API acima.")

    # Exibição dos cards
    col1, = st.columns([1])
    with col1:
        st.markdown(f"**{len(x_final)} produtos filtrados**")
        for p in x_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div class='product-container'>
                    <img src='{img}' width='60' />
                    <div class='product-info'>
                        <a href='{p['url_final']}' target='_blank'><b>{p.get('descricao')}</b></a><br>
                        R$ {p['preco_final']:.2f}
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    components.html(f"<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
