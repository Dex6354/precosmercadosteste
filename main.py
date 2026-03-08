import streamlit as st
import requests
import unicodedata
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurações para Shibata
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

# Links dos logos
LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png" # Logo do Shibata
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"   # Logo do Nagumo
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png" # Imagem padrão


# Funções utilitárias
def remover_acentos(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    """Gera singular/plural automaticamente com regras básicas"""
    variantes = {termo}

    if termo.endswith("s"):
        # Remove o 's' final → bananas → banana
        variantes.add(termo[:-1])
    else:
        # Adiciona 's' no final → tomate → tomates
        variantes.add(termo + "s")

    return list(variantes)
    
def slugify(text):
    """Converte um texto para um slug amigável (usado em URLs)"""
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip() # Remove caracteres especiais, exceto hífens e espaços
    text = re.sub(r'[-\s]+', '-', text) # Substitui espaços e múltiplos hífens por um único hífen
    return text

def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    if match_leve:
        q_rolos = int(match_leve.group(1))
    else:
        match_rolos = re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)
        q_rolos = int(match_rolos.group(1)) if match_rolos else None
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    match_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if match_kg:
        peso = float(match_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if match_g:
        peso = float(match_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = None
    match_unidades = re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)
    if match_unidades:
        qtd_unidades = int(match_unidades.group(1))

    folhas_por_unidade = None
    match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)\s*cada', desc)
    if not match_folhas:
        match_folhas = re.search(r'(\d+)\s*(folhas|toalhas)', desc)
    if match_folhas:
        folhas_por_unidade = int(match_folhas.group(1))

    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        preco_por_folha = preco_total / folhas_leve if folhas_leve else None
        return folhas_leve, preco_por_folha

    match_leve_pague = re.findall(r'(\d+)', desc)
    folhas_leve = None
    if 'leve' in desc and 'folhas' in desc and match_leve_pague:
        folhas_leve = max(int(n) for n in match_leve_pague)

    match_unidades_kit = re.search(r'unidades por kit[:\- ]+(\d+)', desc)
    match_folhas_rolo = re.search(r'quantidade de folhas por (?:rolo|unidade)[:\- ]+(\d+)', desc)
    if match_unidades_kit and match_folhas_rolo:
        total_folhas = int(match_unidades_kit.group(1)) * int(match_folhas_rolo.group(1))
        preco_por_folha = preco_total / total_folhas if total_folhas else None
        return total_folhas, preco_por_folha

    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        preco_por_folha = preco_total / total_folhas if total_folhas else None
        return total_folhas, preco_por_folha

    if folhas_por_unidade:
        preco_por_folha = preco_total / folhas_por_unidade
        return folhas_por_unidade, preco_por_folha

    if folhas_leve:
        preco_por_folha = preco_total / folhas_leve
        return folhas_leve, preco_por_folha

    return None, None


def formatar_preco_unidade_personalizado(preco_total, quantidade, unidade):
    if not unidade:
        return None
    unidade = unidade.lower()
    if quantidade and quantidade != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(quantidade).replace('.', ',')}{unidade.lower()}"
    else:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{unidade.lower()}"

def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        response = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {}).get('produtos', [])
            return [produto for produto in data if produto.get("disponivel", True)]
        else:
            return []
    except:
        return []

def buscar_nagumo(term):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {"Content-Type": "application/json", "Origin": "https://www.nagumo.com", "User-Agent": "Mozilla/5.0"}
    payload = {
        "operationName": "SearchProducts",
        "variables": {"searchProductsInput": {"clientId": "NAGUMO", "storeReference": "22", "currentPage": 1, "pageSize": 50, "search": [{"query": term}], "filters": {}}},
        "query": "query SearchProducts($searchProductsInput: SearchProductsInput!) { searchProducts(searchProductsInput: $searchProductsInput) { products { name price photosUrl sku stock description unit promotion { isActive conditions { price } } } } }"
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.json().get('data', {}).get('searchProducts', {}).get('products', []) or []
    except: return []

def calc_unitario_nagumo(preco, desc, nome, unit_api):
    fonte = f"{nome} {desc}".lower()
    m_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo|g|gramas?)", fonte)
    if m_kg:
        val = float(m_kg.group(1).replace(',', '.'))
        if 'g' in m_kg.group(2) and 'kg' not in m_kg.group(2): val /= 1000
        if val > 0: return f"R$ {preco/val:.2f}/kg", preco/val
    return f"R$ {preco:.2f}/{unit_api or 'un'}", preco

# Configuração da página
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div, span, strong, small { font-size: 0.75rem !important; }
        img { max-width: 100px; height: auto; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6;
            border-radius: 8px; max-width: 480px; margin-left: auto; margin-right: auto;
            background: transparent; scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; }
        .block-container { padding-right: 47px !important; padding-bottom: 15px !important; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)

termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip().lower()
termos_expandidos = gerar_formas_variantes(remover_acentos(termo))

if termo:
    col1, col2 = st.columns(2)

    with st.spinner("🔍 Buscando produtos..."):
        # SHIBATA
        produtos_shibata = []
        max_workers = 8
        max_paginas = 15
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(buscar_pagina_shibata, t, pagina)
                           for t in termos_expandidos
                           for pagina in range(1, max_paginas + 1)]
            for future in as_completed(futures):
                    produtos_shibata.extend(future.result())

        ids_vistos = set()
        produtos_shibata = [p for p in produtos_shibata if p.get('id') not in ids_vistos and not ids_vistos.add(p.get('id'))]
        
        termo_sem_acento = remover_acentos(termo)
        palavras_termo = termo_sem_acento.split()
        produtos_shibata_filtrados = [
            p for p in produtos_shibata
            if all(palavra in remover_acentos(f"{p.get('descricao', '')} {p.get('nome', '')}") for palavra in palavras_termo)
        ]

        produtos_shibata_processados = []
        for p in produtos_shibata_filtrados:
            produto_id = p.get('produto_id') 
            p['url_shibata'] = f"https://www.loja.shibata.com.br/produto/{produto_id}/{slugify(p.get('descricao', 'produto'))}" if produto_id else "https://www.loja.shibata.com.br/"
            
            preco = float(p.get('preco') or 0)
            em_oferta = p.get('em_oferta', False)
            oferta_info = p.get('oferta') or {}
            preco_total = float(oferta_info.get('preco_oferta')) if em_oferta and oferta_info.get('preco_oferta') else preco
            
            p['preco_unidade_val'], _ = calcular_preco_unidade(p.get('descricao', '').lower().replace('grande', ''), preco_total)
            p['preco_por_metro_val'], _ = calcular_precos_papel(p.get('descricao', ''), preco_total)
            produtos_shibata_processados.append(p)

        # Ordenação Shibata
        if 'papel higienico' in termo_sem_acento:
            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=lambda x: x.get('preco_por_metro_val') or float('inf'))
        else:
            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=lambda x: x.get('preco_unidade_val') or float('inf'))

        # NAGUMO
        raw_nagumo = []
        for t in termos_expandidos:
            raw_nagumo.extend(buscar_nagumo(t))
        
        vistos_nagumo = set()
        nagumo_final = []
        for p in raw_nagumo:
            sku = p.get('sku')
            if sku and sku not in vistos_nagumo:
                vistos_nagumo.add(sku)
                nome, desc = p.get('name', ''), p.get('description', '')
                if all(k in remover_acentos(f"{nome} {desc}") for k in palavras_termo):
                    promo = p.get('promotion') or {}
                    cond = promo.get('conditions') or []
                    preco_final = cond[0].get('price') if (promo.get('isActive') and cond) else p.get('price', 0)
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
                    label, sort_v = calc_unitario_nagumo(preco_final, desc, nome, p.get('unit'))
                    p['unit_label'] = label
                    p['sort_val'] = sort_v
                    p['preco_final'] = preco_final
                    nagumo_final.append(p)
        produtos_nagumo_ordenados = sorted(nagumo_final, key=lambda x: x['sort_val'] or 999)

    # Exibição Shibata
    with col1:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_SHIBATA_URL}' width='80' style='background:white; padding:3px; border-radius:4px;'/></h5>", unsafe_allow_html=True)
        for p in produtos_shibata_ordenados:
            desc = p.get('descricao', '')
            # Lógica de cores para Shibata
            if 'papel higienico' in termo_sem_acento:
                desc = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", desc, flags=re.IGNORECASE)
                desc = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", desc, flags=re.IGNORECASE)
            
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_shibata']}' target='_blank' class='product-image'><img src='{img}' width='80'/></a>
                    <div class='product-info'>
                        <a href='{p['url_shibata']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{desc}</b></a><br>
                        <b>R$ {p.get('preco'):.2f}</b>
                    </div>
                </div><hr class='product-separator'/>
            """, unsafe_allow_html=True)

    # Exibição Nagumo
    with col2:
        st.markdown(f"<h5 style='text-align:center;'><img src='{LOGO_NAGUMO_URL}' width='80' style='border:1.5px solid white; border-radius:6px;'/></h5>", unsafe_allow_html=True)
        for p in produtos_nagumo_ordenados:
            nome_nagumo = p['name']
            # Lógica de cores adicionada para Nagumo
            if 'papel higienico' in termo_sem_acento:
                nome_nagumo = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", nome_nagumo, flags=re.IGNORECASE)
                nome_nagumo = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", nome_nagumo, flags=re.IGNORECASE)

            imgs = p.get('photosUrl')
            imagem = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <a href='{p['url_final']}' target='_blank' style='flex: 0 0 auto; text-decoration:none;'>
                        <img src="{imagem}" width="80" style="background-color: white; border-radius: 6px; display: block;"/>
                    </a>
                    <div style="flex: 1; word-break: break-word;">
                        <a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><strong>{nome_nagumo}</strong></a><br>
                        <strong><span style='font-size: 1rem;'>R$ {p['preco_final']:.2f}</span></strong><br>
                        <div style="color: #666;">{p['unit_label']}</div>
                    </div>
                </div><hr class='product-separator' />
            """, unsafe_allow_html=True)
