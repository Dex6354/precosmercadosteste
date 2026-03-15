import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES EXTRAÍDAS DO HAR ---
# URL da página de busca (Next.js App Router)
URL_ACTION = "https://www.xsupermercados.com.br/buscar?texto="
# ID da Server Action identificada no seu log/HAR
ACTION_ID = "b5240a22b66e2990db00381bcd0e987be41e7f34"

HEADERS_X = {
    "Accept": "text/x-component",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "pt-BR,pt;q=0.5",
    "Content-Type": "text/plain;charset=UTF-8",
    "Next-Action": ACTION_ID,
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/buscar?texto=banana",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Priority": "u=1, i"
}

# --- LÓGICA DE EXTRAÇÃO ---
def buscar_x_supermercados(termo):
    # O Next.js Server Action recebe os argumentos como um array formatado em string
    payload = f'["{termo}"]'
    
    try:
        # A requisição deve ser POST para o endpoint da página com o parâmetro de texto
        response = requests.post(
            f"{URL_ACTION}{termo}", 
            headers=HEADERS_X, 
            data=payload, 
            timeout=15
        )
        
        if response.status_code == 200:
            # O Next.js retorna um stream formatado. Procuramos a linha que contém o JSON de sucesso.
            for linha in response.text.split('\n'):
                if '{"success":true' in linha:
                    # Extrair apenas a parte do JSON da linha (removendo o prefixo do stream ex: "1:")
                    json_inicio = linha.find('{')
                    import json
                    data = json.loads(linha[json_inicio:])
                    # No sistema Applay/Next do X, os itens vêm em data -> produtos
                    return data.get('data', {}).get('produtos', []), None
            return [], "Resposta do servidor não continha dados válidos."
        
        return [], f"Erro {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return [], str(e)

# --- UTILITÁRIOS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '-', text)

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="X Supermercados", layout="wide")

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
    
    with st.spinner("A consultar servidor (Server Action)..."):
        produtos_raw, erro = buscar_x_supermercados(termo_input)
        
        if erro:
            st.error(f"Falha: {erro}")
        else:
            # Filtragem manual por palavras-chave
            x_final = [p for p in produtos_raw if all(k in remover_acentos(p.get('nome','')) for k in palavras_chave)]
            
            st.write(f"🔎 Encontrados: {len(x_final)}")
            for p in x_final:
                img = p.get('imagem_principal') or "https://via.placeholder.com/80"
                # Gerar URL amigável do produto
                link = f"https://www.xsupermercados.com.br/produto/{p.get('id')}/{slugify(p.get('nome',''))}"
                
                st.markdown(f"""
                    <div class='product-card'>
                        <img src='{img}' width='80'>
                        <div>
                            <a href='{link}' target='_blank' style='text-decoration:none; color:black;'>
                                <b>{p.get('nome')}</b>
                            </a><br>
                            <span class='price'>R$ {float(p.get('preco_venda', 0)):.2f}</span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

components.html("<script>window.parent.document.querySelectorAll('[data-testid=\"stColumn\"]').forEach(col => col.scrollTop = 0);</script>", height=0)
