import streamlit as st
from streamlit.components.v1 import html

st.set_page_config(layout="wide", page_title="Monitor de Preços (Tentativa de Embed)")

st.title("🛒 Monitor de Preços da Centauro (Via iFrame)")
st.warning("Aviso: A maioria dos sites de e-commerce, como a Centauro, bloqueia a incorporação via iFrame por motivos de segurança (CSP). É provável que você veja uma tela em branco ou uma mensagem de erro de carregamento.")

# Links dos produtos
link1 = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"
link2 = "https://www.centauro.com.br/bermuda-masculina-oxer-mesh-mescla-983436.html?cor=MS"

# Dimensões do iFrame
altura_iframe = 600

# Exibindo os iFrames
col1, col2 = st.columns(2)

with col1:
    st.subheader("Bermuda Oxer Basic")
    # Tentativa de embed usando st.components.v1.iframe
    html_content1 = f'<iframe src="{link1}" width="100%" height="{altura_iframe}px"></iframe>'
    st.components.v1.html(html_content1, height=altura_iframe + 30) # +30 para margem/título

with col2:
    st.subheader("Bermuda Oxer Mesh")
    # Tentativa de embed usando st.components.v1.iframe
    html_content2 = f'<iframe src="{link2}" width="100%" height="{altura_iframe}px"></iframe>'
    st.components.v1.html(html_content2, height=altura_iframe + 30) # +30 para margem/título
