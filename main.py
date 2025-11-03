import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import time

# --- CONFIGURAÇÕES GERAIS ---
URL_CENTAURO = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"
LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Headers robustos para simular o navegador
HEADERS_CENTAURO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://www.centauro.com.br/', 
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0'
}

# --- FUNÇÃO PRINCIPAL DE SCRAPING (Roda no Servidor/Python) ---

def extrair_dados_produto(url):
    """
    Tenta extrair os dados do HTML do produto usando requests e BeautifulSoup.
    """
    log_messages = []
    log_messages.append(f"INICIANDO SCRAPING: {time.strftime('%H:%M:%S')}")
    log_messages.append(f"Tentando requisição GET para a URL: {url}")
    
    try:
        # Usa requests.Session para gerenciar cookies de sessão
        session = requests.Session()
        resposta = session.get(url, headers=HEADERS_CENTAURO, timeout=15)
        
        log_messages.append(f"Status HTTP Recebido: {resposta.status_code}")
        
        if resposta.status_code != 200:
            log_messages.append(f"ERRO: Status {resposta.status_code}. O servidor bloqueou a requisição direta.")
            return {'status': 'erro', 'log': log_messages, 'mensagem': f"Bloqueio HTTP {resposta.status_code}"}

    except requests.exceptions.RequestException as e:
        log_messages.append(f"ERRO: Falha de Conexão. Detalhe: {e}")
        return {'status': 'erro', 'log': log_messages, 'mensagem': f"Falha de conexão: {e}"}

    # --- Análise do HTML ---
    soup = BeautifulSoup(resposta.content, 'html.parser')
    log_messages.append("HTML recebido e pronto para análise.")
    
    dados = {}
    
    # 1. Nome do Produto (H1)
    nome_produto = soup.find('h1', class_='centauro-product-details-2-x-productName') 
    dados['nome'] = nome_produto.text.strip() if nome_produto else 'Não encontrado (Seletor H1)'
    log_messages.append(f"Nome do Produto: {dados['nome']}")

    # 2. Preço de Venda
    preco_element = soup.find('span', class_='centauro-product-price-2-x-sellingPrice') 
    preco_str = preco_element.get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.') if preco_element else None
    try:
        dados['preco_total'] = float(preco_str) if preco_str else 0.0
        log_messages.append(f"Preço Total (Venda): R$ {dados['preco_total']:.2f}")
    except:
        dados['preco_total'] = 'Erro ao converter preço'
        log_messages.append(f"ERRO: Falha ao converter preço de venda: {preco_str}")

    # 3. Preço Antigo/De (Opcional)
    preco_de_element = soup.find('span', class_='centauro-product-price-2-x-listPrice') 
    preco_de_str = preco_de_element.get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.') if preco_de_element else None
    try:
        dados['preco_de'] = float(preco_de_str) if preco_de_str and preco_de_str != preco_str else 0.0
        log_messages.append(f"Preço Antigo ('De'): R$ {dados['preco_de']:.2f}")
    except:
        dados['preco_de'] = 0.0
        
    # 4. Imagem (Meta tag)
    imagem_tag = soup.find('meta', {'property': 'og:image'})
    dados['imagem_url'] = imagem_tag['content'] if imagem_tag else DEFAULT_IMAGE_URL
    log_messages.append(f"URL da Imagem: {dados['imagem_url'][:50]}...")
    
    log_messages.append("SCRAPING CONCLUÍDO COM SUCESSO.")

    dados['status'] = 'sucesso'
    dados['log'] = log_messages
    return dados


# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(
    page_title="Embed Centauro + Log",
    page_icon="🛍️", 
    layout="wide"
)

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
            background-color: #e6ffe6; 
            border: 1px solid #b3ffb3; 
            border-radius: 5px; 
            padding: 15px; 
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛍️ Produto Centauro (Embed + Captura de Dados)</h3>", unsafe_allow_html=True)

# 1. Executa o scraping no servidor (Python)
dados_capturados = extrair_dados_produto(URL_CENTAURO)

# 2. Exibe o Embed e o Botão Lateral
col_embed, col_log = st.columns([2, 1])

with col_embed:
    st.markdown("<h4>Visualização da Página (Embed)</h4>", unsafe_allow_html=True)
    st.markdown(f"**URL:** `{URL_CENTAURO}`")

    # Usa st.components.v1.html para injetar o iframe
    html_iframe = f"""
    <iframe 
        src="{URL_CENTAURO}" 
        width="100%" 
        height="700" 
        style="border: 1px solid #ccc; border-radius: 5px;" 
        title="Produto Centauro"
    >
        O conteúdo foi bloqueado (Same-Origin Policy ou X-Frame-Options).
    </iframe>
    """
    st.components.v1.html(html_iframe, height=750, scrolling=True)

# 3. Exibe o Log de Dados Capturados
with col_log:
    st.markdown("<h4>Dados Capturados pelo Servidor</h4>", unsafe_allow_html=True)
    
    if dados_capturados['status'] == 'sucesso':
        p = dados_capturados
        
        # Cria o resumo dos dados em uma caixa formatada
        resumo_dados = {
            "Nome do Produto": p['nome'],
            "Preço de Venda": f"R$ {p['preco_total']:.2f}",
            "Preço 'De' (Oferta)": f"R$ {p['preco_de']:.2f}" if p['preco_de'] > p['preco_total'] else "Não se aplica",
            "URL da Imagem": f"{p['imagem_url'][:40]}...",
            "Status": "CAPTURA BEM-SUCEDIDA"
        }
        
        st.markdown("<div class='data-card'>", unsafe_allow_html=True)
        for chave, valor in resumo_dados.items():
            st.markdown(f"**{chave}:** {valor}")
        
        # Exibe a imagem capturada para confirmação
        st.image(p['imagem_url'], width=100, caption="Imagem Capturada")
        st.markdown("</div>", unsafe_allow_html=True)
        
    else:
        st.error(f"❌ Falha na Captura: {dados_capturados['mensagem']}")
        
    st.markdown("<h4>Log Detalhado do Servidor</h4>", unsafe_allow_html=True)
    
    # Exibe o log detalhado no campo de log
    log_output = "\n".join(dados_capturados.get('log', ["Log indisponível."]))
    st.markdown(f"<div class='log-box'>{log_output}</div>", unsafe_allow_html=True)
