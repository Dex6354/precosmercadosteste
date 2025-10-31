import streamlit as st

st.set_page_config(page_title="Teste Header", page_icon="🧩")

# CSS para remover cabeçalho e todos os tipos de rodapé (inclusive "Created by / Hosted with Streamlit")
st.markdown("""
<style>
/* Oculta o cabeçalho */
header[data-testid="stHeader"] {
    display: none !important;
}

/* Oculta o rodapé clássico */
footer {
    display: none !important;
    visibility: hidden;
}

/* Oculta a nova barra inferior ("Created by / Hosted with Streamlit") */
div[data-testid="stDecoration"], 
div[data-testid="stStatusWidget"], 
div[data-testid="stFooter"] {
    display: none !important;
    visibility: hidden;
}

/* Remove possíveis margens extras */
section.main > div {
    padding-bottom: 0 !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧩 Teste — Cabeçalho e rodapé ocultos")
st.write("Cabeçalho, rodapé e créditos 'Hosted with Streamlit' foram removidos.")
