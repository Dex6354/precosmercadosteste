import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re

# --- CONFIGURAÇÕES NEXT.JS ---
URL_BUSCA = "https://www.xsupermercados.com.br/buscar?texto="
ACTION_ID = "b5240a22b66e2990db00381bcd0e987be41e7f34"

HEADERS_NEXT = {
    "Accept": "text/x-component",
    "Accept-Language": "pt-BR,pt;q=0.5",
    "Content-Type": "text/plain;charset=UTF-8",
    "Next-Action": ACTION_ID,
    "Next-Router-State-Tree": '["",{"children":["pages",{"children":["search",{"children":["__PAGE__?{\\"texto\\":\\"banana\\"}",{}]}]}]},null,null,true]',
    "Origin": "https://www.xsupermercados.com.br",
    "Referer": "https://www.xsupermercados.com.br/buscar?texto=banana",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# --- FUNÇÃO DE BUSCA ---
def buscar_x_supermercados(termo):
    # O Next.js espera os argumentos da função no corpo como texto puro ou JSON array
    # Baseado no content-length 43, ele envia o termo dentro de um array formatado
    payload = f'["{termo}"]' 
    
    try:
        response = requests.post(
            f"{URL_BUSCA}{termo}", 
            headers=HEADERS_NEXT, 
            data=payload, 
            timeout=15
        )
        
        if response.status_code == 200:
            # O Next.js retorna um formato stream (0:["$@1",null]...)
            # Precisamos extrair o JSON da segunda linha
            linhas = response.text.split('\n')
            for linha in linhas:
                if '{"success":true' in linha:
                    # Remove o prefixo do stream (ex: "1:")
                    json_str = linha[linha.find('{'):]
                    data = requests.utils.json.loads(json_str)
                    return data.get('data', {}).get('produtos', []), None
            
            # Se não achou produtos no stream, tenta extrair o que houver
            return [], "Formato de resposta inesperado do Next.js"
            
        return [], f"Erro {response.status_code}"
    except Exception as e:
        return [], str(e)

# --- UTILITÁRIOS ---
def remover_acentos(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    return re.sub(r'[-\s]+', '-', text)

# --- INTERFACE ---
st.set_page_config(page_title="X Supermercados", layout="wide")

st.markdown("""
    <style>
        .product-card { display: flex; align-items: center; gap: 15px; padding: 10px; border-bottom: 1px solid #eee; }
        .price { color: #2e7d32; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 X Supermercados")
termo_input = st.text_input("Buscar produto:", "Banana").strip()

if termo_input:
    palavras_chave = remover_acentos(termo_input).split()
    
    with st.spinner("Chamando Server Action..."):
        produtos_raw, erro = buscar_x_supermercados(termo_input)
        
        if erro:
            st.error(f"Erro: {erro}")
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
