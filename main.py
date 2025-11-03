import streamlit as st

# --- CONFIGURAÇÕES GERAIS ---
URL_CENTAURO = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"
LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"

# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(
    page_title="Acesso Direto Centauro",
    page_icon="🛍️", 
    layout="centered" # Centralizado para melhor visualização
)

st.markdown("""
    <style>
        .block-container { padding-top: 5rem; }
        footer, #MainMenu { visibility: hidden; }
        .logo-centauro { display: block; margin: 0 auto 20px auto; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h3>🛍️ Acesso Direto ao Produto Centauro</h3>", unsafe_allow_html=True)

# Exibe o logo
st.image(LOGO_CENTAURO_URL, width=150)

st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <p>Acesse o produto diretamente no site da Centauro clicando no botão abaixo:</p>
        <p style="font-size: 0.8em; color: gray;">
            {URL_CENTAURO}
        </p>
    </div>
""", unsafe_allow_html=True)

# Botão principal que abre a URL em uma nova aba
st.link_button(
    label="🔗 Abrir Página da Bermuda",
    url=URL_CENTAURO,
    type="primary",
    use_container_width=True
)

st.markdown("""
    <div style="margin-top: 50px; padding: 10px; border-top: 1px solid #eee; font-size: 0.8em; color: #666; text-align: center;">
        Este aplicativo não realiza scraping, apenas redireciona para a URL especificada,
        evitando qualquer bloqueio de servidor (403).
    </div>
""", unsafe_allow_html=True)
