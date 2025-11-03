import streamlit as st
from streamlit.components.v1 import html

# Configuração básica da página
st.set_page_config(
    layout="wide", 
    page_title="Monitor de Preços - Embed Centauro"
)

st.title("🔗 Monitor de Preços (Tentativa de Embed Direto)")

# --- AVISO IMPORTANTE ---
st.warning(
    "**ATENÇÃO:** A incorporação direta de sites de e-commerce (como a Centauro) usando `<iframe>` é frequentemente bloqueada por políticas de segurança (CSP). Se você ver uma tela em branco ou um erro de carregamento, significa que o site bloqueou a visualização interna. Neste caso, a Opção 2 (Web Scraping) seria a alternativa funcional."
)

# Dimensões para a visualização (ajuste conforme necessário)
ALTURA_IFRAME = 700  # Altura em pixels para a visualização
LARGURA_IFRAME = "100%" # Largura total da coluna

# -------------------------------------------------------------------
# 1. EMBED PARA O PRIMEIRO PRODUTO
# -------------------------------------------------------------------
st.header("Bermuda Oxer Basic")
link1 = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"

st.markdown(f"**Link Original:** [{link1}]({link1})", unsafe_allow_html=True)

# Criação do conteúdo HTML para o iFrame
# Adicionamos um buffer de altura (+30) para acomodar títulos/espaçamento no Streamlit
html_content1 = f'<iframe src="{link1}" width="{LARGURA_IFRAME}" height="{ALTURA_IFRAME}px"></iframe>'

# Exibe o componente HTML/iFrame
# O `height` do st.components.v1.html precisa ser ligeiramente maior que a altura do iFrame
st.components.v1.html(html_content1, height=ALTURA_IFRAME + 30)

# -------------------------------------------------------------------
# SEPARADOR VISUAL
# -------------------------------------------------------------------
st.markdown("---")

# -------------------------------------------------------------------
# 2. EMBED PARA O SEGUNDO PRODUTO
# -------------------------------------------------------------------
st.header("Bermuda Oxer Mesh")
link2 = "https://www.centauro.com.br/bermuda-masculina-oxer-mesh-mescla-983436.html?cor=MS"

st.markdown(f"**Link Original:** [{link2}]({link2})", unsafe_allow_html=True)

# Criação do conteúdo HTML para o iFrame
html_content2 = f'<iframe src="{link2}" width="{LARGURA_IFRAME}" height="{ALTURA_IFRAME}px"></iframe>'

# Exibe o componente HTML/iFrame
st.components.v1.html(html_content2, height=ALTURA_IFRAME + 30)
