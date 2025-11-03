import streamlit as st
import requests
from bs4 import BeautifulSoup

st.set_page_config(layout="centered", page_title="Monitor de Preços (Scraping)")

st.title("💰 Monitor de Preços - Centauro (Via Scraping)")

# URLs
urls = {
    "Bermuda Oxer Basic": "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04",
    "Bermuda Oxer Mesh": "https://www.centauro.com.br/bermuda-masculina-oxer-mesh-mescla-983436.html?cor=MS"
}

def extrair_preco(url):
    """Tenta extrair o preço da URL usando requests e BeautifulSoup."""
    try:
        # Adiciona um User-Agent para parecer um navegador real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Levanta um erro para códigos de status ruins (4xx ou 5xx)

        soup = BeautifulSoup(response.content, 'html.parser')

        # --- ATENÇÃO: ESTE SELETOR É UM CHUTE E DEVE SER VERIFICADO NO SITE REAL ---
        # Geralmente, preços estão em tags específicas com classes como 'price', 'current-price', etc.
        # Eu estou usando um placeholder comum. Você precisa inspecionar o site para encontrar a classe correta.
        
        # Exemplo de seletor que você *poderia* ter que ajustar:
        preco_tag = soup.find('span', class_='Price-sc-15437d31-2') # **MUDE ISSO PARA O SELETOR REAL**
        
        if preco_tag:
            preco = preco_tag.text.strip()
            return preco
        else:
            return "Preço não encontrado (Seletor incorreto?)"

    except requests.exceptions.RequestException as e:
        return f"Erro de conexão: {e}"
    except Exception as e:
        return f"Erro inesperado: {e}"

# Dicionário para armazenar os resultados
precos_atuais = {}

# Coletando os dados
with st.spinner('Coletando preços...'):
    for nome, url in urls.items():
        precos_atuais[nome] = extrair_preco(url)

# --- Exibição dos Resultados ---

st.header("Preços Atualizados:")

dados_tabela = []
for nome, preco in precos_atuais.items():
    dados_tabela.append({
        "Produto": nome,
        "Preço Atual": preco,
        "Link": urls[nome]
    })

# Criação da Tabela no Streamlit
st.table(dados_tabela)

st.info("Lembre-se de inspecionar o site da Centauro para encontrar o seletor CSS correto e atualizar a linha `preco_tag = soup.find(...)` no código para garantir a extração correta do preço.")
