import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json

# --- CONFIGURAÇÕES GERAIS ---
URL_CENTAURO = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"
LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"

# Headers robustos para simular o navegador e tentar evitar o 403
HEADERS_CENTAURO = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept-Language': 'pt-BR,pt;q=0.9',
    'Referer': 'https://www.centauro.com.br/', 
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0'
}

# --- FUNÇÃO PRINCIPAL DE SCRAPING ---

def extrair_produto_centauro(url):
    """
    Simula o ciclo de cookies anti-bot (Akamai) e tenta extrair os dados do HTML.
    Esta lógica é a melhor chance de sucesso sem usar Selenium.
    """
    
    # 1. Primeira requisição para obter cookies de segurança
    print("Tentativa 1: Obtendo cookies de segurança...")
    try:
        # Usamos requests.Session para gerenciar cookies automaticamente
        session = requests.Session()
        resposta_cookie = session.get(url, headers=HEADERS_CENTAURO, timeout=15)
        
        if resposta_cookie.status_code == 200 and 'vtex' in resposta_cookie.text.lower():
            print("   -> Sucesso direto na primeira requisição!")
            resposta_final = resposta_cookie
        elif resposta_cookie.status_code == 403:
            # Akamai ou VTex exigem a volta dos cookies.
            print(f"   -> Recebido 403/Bloqueio. Tentando nova requisição com cookies de sessão...")
            
            # A Session já carrega os cookies no objeto `session`
            resposta_final = session.get(url, headers=HEADERS_CENTAURO, timeout=15)
            
            if resposta_final.status_code != 200:
                print(f"   -> Tentativa com cookie falhou. Status final: {resposta_final.status_code}")
                raise requests.exceptions.HTTPError(f"Bloqueado: {resposta_final.status_code}")
            else:
                print("   -> Sucesso na segunda requisição com cookies!")
        else:
             resposta_final = resposta_cookie
             resposta_final.raise_for_status()

    except requests.exceptions.RequestException as e:
        return {'status': 'erro', 'mensagem': f"Falha de Conexão/Bloqueio: {e}"}

    # 2. Análise do HTML (Lógica do Shibata/Nagumo)
    
    soup = BeautifulSoup(resposta_final.content, 'html.parser')
    
    # Nome do Produto (H1)
    nome_produto = soup.find('h1', class_='centauro-product-details-2-x-productName') 
    nome_str = nome_produto.text.strip() if nome_produto else 'Não encontrado'

    # Preço de Venda
    # Seletor do preço: span[data-testid="selling-price"] ou span.centauro-product-price-2-x-sellingPrice
    preco_element = soup.find('span', class_='centauro-product-price-2-x-sellingPrice') 
    preco_str = preco_element.get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.') if preco_element else None
    preco_total = float(preco_str) if preco_str else 0.0

    # Preço Antigo/De (Opcional)
    preco_de_element = soup.find('span', class_='centauro-product-price-2-x-listPrice') 
    preco_de_str = preco_de_element.get_text(strip=True).replace('R$', '').replace('.', '').replace(',', '.') if preco_de_element else None
    preco_de = float(preco_de_str) if preco_de_str and preco_de_str != preco_str else 0.0
    
    # Imagem (Meta tag ou seletor principal)
    imagem_tag = soup.find('meta', {'property': 'og:image'})
    imagem_url = imagem_tag['content'] if imagem_tag else DEFAULT_IMAGE_URL

    # SKU / ID (Pode estar em JSON LD Script)
    sku = 'Não encontrado'
    script_json = soup.find('script', {'type': 'application/ld+json'})
    if script_json:
        try:
            data_json = json.loads(script_json.string)
            if isinstance(data_json, list): data_json = data_json[0] # Se for lista
            sku = data_json.get('sku') or data_json.get('productID', 'Não encontrado')
        except:
            pass
    
    # --- LÓGICA DE RETORNO (Simulando Shibata/Nagumo) ---
    # Centauro vende por "unidade". Não há cálculo por KG/L.
    
    preco_unitario_val = preco_total if preco_total > 0 else float('inf')
    preco_unitario_str = f"R$ {preco_total:.2f}/unidade"
    
    if preco_de > preco_total:
        desconto = round(100 * (preco_de - preco_total) / preco_de)
        oferta_info = f"<span style='color:red; font-weight: bold;'>({desconto}% OFF)</span>"
        preco_de_str = f"<span style='text-decoration: line-through; color:gray; font-size: 0.9em;'>R$ {preco_de:.2f}</span>"
    else:
        oferta_info = ""
        preco_de_str = ""
        
    return {
        'status': 'sucesso',
        'nome': nome_str,
        'sku': sku,
        'preco_total': preco_total,
        'preco_de': preco_de,
        'preco_unitario_val': preco_unitario_val,
        'preco_unitario_str': preco_unitario_str,
        'em_oferta': preco_de > preco_total,
        'oferta_info': oferta_info,
        'preco_de_str': preco_de_str,
        'imagem_url': imagem_url,
        'url_centauro': url
    }


# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(page_title="Preço Centauro", page_icon="🛍️", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        footer, #MainMenu { visibility: hidden; }
        .product-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 20px auto;
        }
        .logo-centauro {
            display: block;
            margin: 0 auto 15px auto;
        }
        .produto-info h2 { font-size: 1.2rem; margin-top: 0; }
        .preco-atual { font-size: 1.8rem; font-weight: bold; color: #008000; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛍️ Preço da Bermuda Centauro</h3>", unsafe_allow_html=True)

# Link de onde a informação está vindo
st.markdown(f"<small>🔗 Link alvo: <a href='{URL_CENTAURO}' target='_blank'>{URL_CENTAURO}</a></small>", unsafe_allow_html=True)


with st.spinner("🔍 Buscando dados do produto na Centauro..."):
    dados_produto = extrair_produto_centauro(URL_CENTAURO)

if dados_produto['status'] == 'sucesso':
    p = dados_produto
    
    preco_html = f"<div class='preco-atual'>R$ {p['preco_total']:.2f}</div>"
    preco_html += f"<div>{p['preco_de_str']} {p['oferta_info']}</div>"
    
    st.markdown(f"""
        <div class='product-card'>
            <img src="{LOGO_CENTAURO_URL}" width="120" alt="Centauro" class="logo-centauro"/>
            <hr>
            <div class='produto-info'>
                <a href='{p['url_centauro']}' target='_blank' style='text-decoration:none; color:inherit;'>
                    <h2>{p['nome']}</h2>
                </a>
                <div style="text-align: center;">
                    <img src="{p['imagem_url']}" width="200" style="margin: 10px 0; border-radius: 4px;"/>
                </div>
                <div style="margin-top: 15px; text-align: center;">
                    {preco_html}
                    <div style="margin-top: 5px; font-size: 0.9em; color: #666;">{p['preco_unitario_str']}</div>
                    <div style="margin-top: 15px; font-size: 0.8em; color: gray;">SKU: {p['sku']}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
else:
    st.error(f"❌ Não foi possível obter os dados da Centauro.")
    st.warning(f"Detalhe do erro: {dados_produto['mensagem']}")
    st.info("A Centauro utiliza um sistema anti-bot forte (Akamai) que bloqueia o acesso direto do servidor (Render). Isso causa o erro 403. A solução mais robusta seria usar um proxy rotativo ou um serviço de scraping externo.")
