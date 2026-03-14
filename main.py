import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import json

# --- CONFIGURAÇÕES ---
LOGO_ATACADAO_URL = "https://upload.wikimedia.org/wikipedia/pt/d/d3/Atacad%C3%A3o_logo.png"

def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    # Lógica simplificada para KG/L/Unidade
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo|g|gramas?)', desc_minus)
    if m_kg:
        valor = float(m_kg.group(1).replace(',', '.'))
        if 'g' in m_kg.group(2) and 'kg' not in m_kg.group(2):
            valor = valor / 1000
        return preco_total / valor, f"R$ {preco_total / valor:.2f}/kg"
    return None, None

# --- FUNÇÃO DE BUSCA COM DEBUGGER ---
def buscar_atacadao_debug(termo):
    # Endpoint alternativo mais comum em lojas VTEX
    url = f"https://www.atacadao.com.br/api/catalog_system/pub/products/search?ft={termo}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "application/json"
    }
    
    debug_info = {"url": url, "status": None, "response": None, "error": None}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        debug_info["status"] = r.status_code
        if r.status_code == 200:
            data = r.json()
            debug_info["response"] = data
            return data, debug_info
        else:
            debug_info["error"] = f"Erro HTTP: {r.status_code}"
    except Exception as e:
        debug_info["error"] = str(e)
    
    return [], debug_info

# --- INTERFACE ---
st.set_page_config(page_title="Atacadão Debugger", layout="wide")

# Estilo otimizado para Celular (Fontes maiores e containers flexíveis)
st.markdown("""
    <style>
        .product-card {
            border: 1px solid #ddd; padding: 10px; border-radius: 10px; margin-bottom: 10px;
            display: flex; align-items: center; background: white;
        }
        .price { color: #d32f2f; font-weight: bold; font-size: 1.2rem; }
        .debug-box { background: #f0f2f6; padding: 10px; border-radius: 5px; font-family: monospace; font-size: 10px; overflow-x: auto; }
    </style>
""", unsafe_allow_html=True)

st.title("🛒 Atacadão Search")

# Checkbox de Debugger
enable_debug = st.checkbox("Ativar Modo Debugger (Ver dados crus)")

termo_busca = st.text_input("Produto:", "Banana")

if termo_busca:
    produtos_raw, info = buscar_atacadao_debug(termo_busca)
    
    if enable_debug:
        st.subheader("🛠 Informações de Debug")
        st.write(f"**URL chamada:** {info['url']}")
        st.write(f"**Status Code:** {info['status']}")
        if info['error']: st.error(info['error'])
        if info['response']:
            with st.expander("Ver JSON completo recebido"):
                st.json(info['response'])

    if not produtos_raw:
        st.warning("Nenhum item retornado. Tente outro termo ou verifique o Debugger.")
    else:
        st.success(f"Exibindo {len(produtos_raw)} resultados")
        
        for p in produtos_raw:
            try:
                nome = p.get('productName', 'Sem nome')
                link = p.get('link', '#')
                # No padrão VTEX, o preço fica em items > sellers > commertialOffer
                item_zero = p.get('items', [{}])[0]
                img = item_zero.get('images', [{}])[0].get('imageUrl', '')
                
                seller = item_zero.get('sellers', [{}])[0]
                preco = seller.get('commertialOffer', {}).get('Price', 0)
                
                calc_val, calc_label = calcular_preco_unidade(nome, preco)
                
                st.markdown(f"""
                    <div class="product-card">
                        <img src="{img}" width="80" style="margin-right:15px">
                        <div style="flex:1">
                            <a href="{link}" style="text-decoration:none; color:black"><strong>{nome}</strong></a><br>
                            <span class="price">R$ {preco:.2f}</span><br>
                            <small>{calc_label if calc_label else ""}</small>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                if enable_debug: st.write(f"Erro ao processar item: {e}")

# Script para Android (ajuste de viewport/scroll)
components.html("<script>window.scrollTo(0,0);</script>", height=0)
