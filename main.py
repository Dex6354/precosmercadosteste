import streamlit as st

# --- CONFIGURAÇÕES GERAIS ---
URL_CENTAURO = "https://www.centauro.com.br/bermuda-masculina-oxer-ls-basic-new-984889.html?cor=04"
LOGO_CENTAURO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-centauro.png"

# --- APLICAÇÃO STREAMLIT ---

st.set_page_config(
    page_title="Embed Centauro",
    page_icon="🛍️", 
    layout="wide" # Layout wide é melhor para iframes
)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; }
        footer, #MainMenu { visibility: hidden; }
        .logo-centauro { display: block; margin: 0 auto 10px auto; }
        /* Estilo para o aviso de bloqueio */
        .aviso-iframe {
            background-color: #fff3cd; 
            color: #856404; 
            border: 1px solid #ffeeba; 
            border-radius: 5px; 
            padding: 15px; 
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown(f"<h3>🛍️ Produto Centauro (URL: <a href='{URL_CENTAURO}' target='_blank'>Abrir em Nova Aba</a>)</h3>", unsafe_allow_html=True)

st.markdown(f"""
    <div class="aviso-iframe">
        <strong>Aviso Técnico:</strong> A Centauro (e a maioria dos grandes varejistas) 
        bloqueia a incorporação da página em sites de terceiros por motivos de segurança (X-Frame-Options/CSP). 
        Se você vir um espaço em branco ou um erro no frame abaixo, este bloqueio está ativo.
        Recomendamos clicar no link acima para abrir em uma nova aba.
    </div>
""", unsafe_allow_html=True)

# Container para o embed
st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
st.image(LOGO_CENTAURO_URL, width=100, use_column_width=False, output_format="PNG")
st.markdown("</div>", unsafe_allow_html=True)

# Usa st.components.v1.html para injetar o iframe
html_iframe = f"""
<iframe 
    src="{URL_CENTAURO}" 
    width="100%" 
    height="800" 
    style="border: 1px solid #ccc; border-radius: 5px;" 
    title="Produto Centauro"
>
    Seu navegador não suporta iframes, ou o conteúdo foi bloqueado.
</iframe>
"""

st.components.v1.html(html_iframe, height=850, scrolling=True)
