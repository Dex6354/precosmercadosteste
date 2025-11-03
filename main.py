import streamlit as st
import requests
import json
from bs4 import BeautifulSoup
import time
import re

# --- CONFIGURAÇÕES GERAIS ---
PRODUTO_ID = "984889"
COR_ID = "04"
URL_CENTAURO_WEB = f"https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-{PRODUTO_ID}.html?cor={COR_ID}"

LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Headers mais robustos para simular um navegador legítimo
HEADERS_CENTAURO = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": "https://www.centauro.com.br/", 
    "Connection": "keep-alive",
}

# --- FUNÇÃO PRINCIPAL: CAPTURA DE DADOS VIA JSON-LD (Servidor) ---

def buscar_centauro_jsonld(url_web):
    log_messages = []
    log_messages.append(f"INICIANDO ÚLTIMA TENTATIVA: JSON-LD (Schema.org) no HTML principal. {time.strftime('%H:%M:%S')}")
    log_messages.append(f"Tentando requisição GET para a URL Web: {url_web}")
    
    try:
        resposta = requests.get(url_web, headers=HEADERS_CENTAURO, timeout=15)
        
        log_messages.append(f"Status HTTP Recebido: {resposta.status_code}")
        
        if resposta.status_code == 403:
            log_messages.append("ERRO FATAL: O servidor Centauro retornou 403 (Forbidden).")
            log_messages.append("O anti-bot está bloqueando TODAS as requisições de servidor (HTML e API).")
            return {'status': 'erro', 'log': log_messages, 'mensagem': f"Bloqueio de Servidor Total: 403 Forbidden."}

        if resposta.status_code != 200:
            log_messages.append(f"ERRO: Status {resposta.status_code}. Falha na requisição.")
            return {'status': 'erro', 'log': log_messages, 'mensagem': f"Bloqueio HTTP {resposta.status_code}"}

    except requests.exceptions.RequestException as e:
        log_messages.append(f"ERRO: Falha de Conexão. Detalhe: {e}")
        return {'status': 'erro', 'log': log_messages, 'mensagem': f"Falha de conexão: {e}"}

    # --- Análise do HTML para JSON-LD ---
    soup = BeautifulSoup(resposta.content, 'html.parser')
    log_messages.append("HTML recebido. Procurando bloco <script type='application/ld+json'>.")
    
    script_json = soup.find('script', {'type': 'application/ld+json'})
    
    if not script_json:
        log_messages.append("JSON-LD NÃO ENCONTRADO no HTML. A página está vazia ou o script foi injetado via JS (não rastreável por requests).")
        return {'status': 'erro', 'log': log_messages, 'mensagem': "JSON-LD não encontrado no HTML estático."}

    # Tenta carregar o JSON-LD
    try:
        data_json = json.loads(script_json.string)
        # Se for uma lista de JSON-LDs, pega o primeiro ou o que tiver o tipo 'Product'
        if isinstance(data_json, list):
            data_json = next((item for item in data_json if item.get('@type') == 'Product'), data_json[0])
            
        log_messages.append("JSON-LD encontrado e parseado com sucesso.")

        # Extração de dados
        dados = {}
        dados['nome'] = data_json.get('name', 'N/D no JSON-LD')
        dados['sku'] = data_json.get('sku', 'N/D no JSON-LD')
        dados['imagem_url'] = data_json.get('image', DEFAULT_IMAGE_URL)
        
        # Oferta (pode estar em 'offers')
        offers = data_json.get('offers', {})
        if isinstance(offers, list): offers = offers[0] if offers else {}

        preco_total = float(offers.get('price', 0.0))
        preco_de = float(data_json.get('listPrice', 0.0) or 0.0) # Tentativa de achar listPrice
        if not preco_de and offers.get('priceSpecification'):
             # Tenta extrair preço original de especificações de preço (VTEX)
             for spec in offers['priceSpecification']:
                 if spec.get('priceType') == 'ListPrice':
                     preco_de = float(spec.get('price', 0.0))
                     break
                     
        dados['preco_total'] = preco_total
        dados['preco_de'] = preco_de
        
        log_messages.append(f"Produto Capturado: {dados['nome']}")
        log_messages.append(f"Preço de Venda: R$ {dados['preco_total']:.2f}")
        log_messages.append(f"Preço Antigo: R$ {dados['preco_de']:.2f}")

    except Exception as e:
        log_messages.append(f"ERRO: Falha ao extrair/converter dados do JSON-LD. Detalhe: {e}")
        return {'status': 'erro', 'log': log_messages, 'mensagem': "Falha ao analisar JSON-LD."}

    log_messages.append("CAPTURA JSON-LD CONCLUÍDA.")
    dados['status'] = 'sucesso'
    dados['log'] = log_messages
    return dados


# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(
    page_title="Embed Centauro + Log",
    page_icon="🛍️", 
    layout="wide"
)

# Estilos CSS
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        footer, #MainMenu { visibility: hidden; }
        .log-box {
            background-color: #f8f8f8;
            border: 1px solid #e0e0e0;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            max-height: 400px;
            font-family: monospace;
            white-space: pre;
            font-size: 0.8em;
        }
        .data-card-success {
            background-color: #e6ffe6; 
            border: 1px solid #b3ffb3; 
            border-radius: 5px; 
            padding: 15px; 
            margin-bottom: 20px;
        }
        .data-card-error {
            background-color: #ffe6e6; 
            border: 1px solid #ffb3b3; 
            border-radius: 5px; 
            padding: 15px; 
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛍️ Bermuda Centauro (Embed + Log)</h3>", unsafe_allow_html=True)

# 1. Executa a busca (JSON-LD) no servidor (Python)
dados_capturados = buscar_centauro_jsonld(URL_CENTAURO_WEB)

col_embed, col_log = st.columns([2, 1])

with col_embed:
    st.markdown("<h4>Visualização da Página (Embed)</h4>", unsafe_allow_html=True)
    st.markdown(f"**URL:** `{URL_CENTAURO_WEB}`")

    st.warning("O conteúdo é visível aqui (Embed), mas o código Streamlit NÃO PODE ler o preço ou nome devido à Política de Mesma Origem (SOP) do navegador. A captura dos dados depende EXCLUSIVAMENTE do Log ao lado.")

    html_iframe = f"""
    <iframe 
        src="{URL_CENTAURO_WEB}" 
        width="100%" 
        height="700" 
        style="border: 1px solid #ccc; border-radius: 5px;" 
        title="Produto Centauro"
    >
        O conteúdo foi bloqueado.
    </iframe>
    """
    st.components.v1.html(html_iframe, height=750, scrolling=True)

# 2. Exibe o Log de Dados Capturados
with col_log:
    st.markdown("<h4>Dados Capturados pelo Servidor</h4>", unsafe_allow_html=True)
    
    if dados_capturados['status'] == 'sucesso':
        p = dados_capturados
        
        preco_atual_str = f"R$ {p['preco_total']:.2f}"
        preco_de_str = ""
        oferta_info = ""
        
        if p['preco_de'] > p['preco_total']:
            desconto = round(100 * (p['preco_de'] - p['preco_total']) / p['preco_de'])
            preco_de_str = f"<span style='text-decoration: line-through; color:gray;'>R$ {p['preco_de']:.2f}</span>"
            oferta_info = f"<span style='color:red; font-weight: bold;'>({desconto}% OFF)</span>"

        st.markdown("<div class='data-card-success'>", unsafe_allow_html=True)
        st.markdown(f"**Nome:** {p['nome']}")
        st.markdown(f"**Preço Atual:** <span style='font-size:1.5em;'>{preco_atual_str}</span> {oferta_info}", unsafe_allow_html=True)
        st.markdown(f"**Preço 'De':** {preco_de_str}", unsafe_allow_html=True)
        st.markdown(f"**Status:** CAPTURA JSON-LD BEM-SUCEDIDA")
        
        st.image(p['imagem_url'], width=100, caption="Imagem Capturada")
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.markdown("<div class='data-card-error'>", unsafe_allow_html=True)
        st.error(f"❌ Falha de Captura: {dados_capturados['mensagem']}")
        st.markdown(f"**Causa:** O servidor Centauro está bloqueando TODAS as requisições de servidor (HTML, API e JSON-LD) com **403 Forbidden**. A captura é impossível com métodos simples.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("<h4>Log Completo da Tentativa</h4>", unsafe_allow_html=True)
    log_output = "\n".join(dados_capturados.get('log', ["Log indisponível."]))
    st.markdown(f"<div class='log-box'>{log_output}</div>", unsafe_allow_html=True)
