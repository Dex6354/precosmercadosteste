import streamlit as st
import requests
import json
import time

# --- CONFIGURAÇÕES GERAIS ---
PRODUTO_ID = "984889"
COR_ID = "04"
URL_CENTAURO_WEB = f"https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-{PRODUTO_ID}.html?cor={COR_ID}"
URL_CENTAURO_API = f"https://apigateway.centauro.com.br/centauro-bff/products/{PRODUTO_ID}?color={COR_ID}"

LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Headers extraídos da requisição de sucesso (chave para o bypass 403)
HEADERS_CENTAURO_API = {
    "accept": "*/*",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "pt-BR,pt;q=0.9",
    # O Origin e Referer são cruciais para simular um acesso legítimo
    "origin": "https://www.centauro.com.br", 
    "referer": "https://www.centauro.com.br/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "authority": "apigateway.centauro.com.br",
}

# --- FUNÇÃO PRINCIPAL: CAPTURA DE DADOS VIA API JSON ---

def buscar_centauro_api(url_api):
    log_messages = []
    log_messages.append(f"INICIANDO CAPTURA VIA API JSON: {time.strftime('%H:%M:%S')}")
    log_messages.append(f"Chamando API: {url_api}")
    
    try:
        resposta = requests.get(url_api, headers=HEADERS_CENTAURO_API, timeout=10)
        
        log_messages.append(f"Status HTTP Recebido: {resposta.status_code}")
        
        if resposta.status_code != 200:
            log_messages.append(f"ERRO: API retornou Status {resposta.status_code}. Headers insuficientes ou URL incorreta.")
            return {'status': 'erro', 'log': log_messages, 'mensagem': f"API Status {resposta.status_code}"}
        
        # Tenta carregar o JSON
        try:
            dados_json = resposta.json()
            log_messages.append("Resposta JSON recebida e parseada com sucesso.")
        except json.JSONDecodeError:
            log_messages.append("ERRO: Resposta não é um JSON válido.")
            return {'status': 'erro', 'log': log_messages, 'mensagem': "API não retornou JSON válido."}

    except requests.exceptions.RequestException as e:
        log_messages.append(f"ERRO: Falha de Conexão. Detalhe: {e}")
        return {'status': 'erro', 'log': log_messages, 'mensagem': f"Falha de conexão: {e}"}

    # --- Análise e Extração dos Dados do JSON ---
    dados = {}
    
    # Nome do Produto
    dados['nome'] = dados_json.get('name', 'Nome não encontrado no JSON')
    
    # Preços (Vtex-like structure)
    skus = dados_json.get('skus', [])
    if skus:
        sku_selecionado = skus[0] # Pega o primeiro SKU (geralmente o padrão)
        
        # Preço Atual (currentPrice)
        preco_total = sku_selecionado.get('currentPrice', 0.0)
        dados['preco_total'] = float(preco_total)
        
        # Preço Antigo (listPrice)
        preco_de = sku_selecionado.get('listPrice', 0.0)
        dados['preco_de'] = float(preco_de)
        
        # Estoque
        dados['estoque'] = sku_selecionado.get('stockQuantity', 0)
        
    else:
        dados['preco_total'] = 0.0
        dados['preco_de'] = 0.0
        dados['estoque'] = 'N/D'

    # Imagem
    imagens = dados_json.get('images', [])
    dados['imagem_url'] = imagens[0].get('path') if imagens else DEFAULT_IMAGE_URL
    
    log_messages.append(f"Produto Capturado: {dados['nome']}")
    log_messages.append(f"Preço de Venda: R$ {dados['preco_total']:.2f}")
    log_messages.append(f"Preço Antigo: R$ {dados['preco_de']:.2f}")
    log_messages.append(f"Estoque: {dados['estoque']}")
    log_messages.append("CAPTURA API CONCLUÍDA.")

    dados['status'] = 'sucesso'
    dados['log'] = log_messages
    return dados


# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(
    page_title="Embed Centauro + API Log",
    page_icon="🛍️", 
    layout="wide"
)

# Estilos CSS (mantidos do anterior para formatação)
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
        .data-card {
            background-color: #e6ffe6; /* Cor verde para sucesso */
            border: 1px solid #b3ffb3; 
            border-radius: 5px; 
            padding: 15px; 
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛍️ Bermuda Centauro (Embed + API JSON Capture)</h3>", unsafe_allow_html=True)

# 1. Executa a busca via API no servidor (Python)
dados_capturados = buscar_centauro_api(URL_CENTAURO_API)

col_embed, col_log = st.columns([2, 1])

with col_embed:
    st.markdown("<h4>Visualização da Página (Embed)</h4>", unsafe_allow_html=True)
    st.markdown(f"**URL:** `{URL_CENTAURO_WEB}`")

    # Usa st.components.v1.html para injetar o iframe
    html_iframe = f"""
    <iframe 
        src="{URL_CENTAURO_WEB}" 
        width="100%" 
        height="700" 
        style="border: 1px solid #ccc; border-radius: 5px;" 
        title="Produto Centauro"
    >
        O conteúdo foi bloqueado (Same-Origin Policy ou X-Frame-Options).
    </iframe>
    """
    st.components.v1.html(html_iframe, height=750, scrolling=True)

# 2. Exibe o Log de Dados Capturados
with col_log:
    st.markdown("<h4>Dados Capturados pelo Servidor (API)</h4>", unsafe_allow_html=True)
    
    if dados_capturados['status'] == 'sucesso':
        p = dados_capturados
        
        # Formata o resumo dos dados
        preco_atual_str = f"R$ {p['preco_total']:.2f}"
        preco_de_str = ""
        oferta_info = ""
        
        if p['preco_de'] > p['preco_total']:
            desconto = round(100 * (p['preco_de'] - p['preco_total']) / p['preco_de'])
            preco_de_str = f"<span style='text-decoration: line-through; color:gray;'>R$ {p['preco_de']:.2f}</span>"
            oferta_info = f"<span style='color:red; font-weight: bold;'>({desconto}% OFF)</span>"

        st.markdown("<div class='data-card'>", unsafe_allow_html=True)
        st.markdown(f"**Nome:** {p['nome']}")
        st.markdown(f"**Preço Atual:** <span style='font-size:1.5em;'>{preco_atual_str}</span> {oferta_info}", unsafe_allow_html=True)
        st.markdown(f"**Preço 'De':** {preco_de_str}", unsafe_allow_html=True)
        st.markdown(f"**Estoque:** {p['estoque']}")
        st.markdown(f"**Status:** CAPTURA VIA API BEM-SUCEDIDA")
        
        # Exibe a imagem capturada para confirmação
        st.image(p['imagem_url'], width=100, caption="Imagem Capturada")
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.error(f"❌ Falha na Captura via API: {dados_capturados['mensagem']}")
        
    st.markdown("<h4>Log Completo da API</h4>", unsafe_allow_html=True)
    
    # Exibe o log detalhado no campo de log
    log_output = "\n".join(dados_capturados.get('log', ["Log indisponível."]))
    st.markdown(f"<div class='log-box'>{log_output}</div>", unsafe_allow_html=True)
