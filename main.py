import streamlit as st

st.set_page_config(page_title="Teste Header", page_icon="🧩")

# CSS para remover cabeçalho e rodapé (footer)
st.markdown("""
<style>
/* Oculta o cabeçalho */
header[data-testid="stHeader"] {
    display: none;
}

/* Oculta o rodapé padrão do Streamlit */
footer {
    display: none;
}

/* Oculta também a barra inferior de "Made with Streamlit" */
div[data-testid="stStatusWidget"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧩 Teste — Cabeçalho e rodapé ocultos")
st.write("O cabeçalho e o rodapé originais do Streamlit foram removidos com CSS.")
