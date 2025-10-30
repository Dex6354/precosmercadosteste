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

# Funções utilitárias
def remover_acentos(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    """Gera singular/plural automaticamente com regras básicas"""
    variantes = {termo}

    if termo.endswith("s"):
        # Remove o 's' final → banana**s** → banana
        variantes.add(termo[:-1])
    else:
        # Adiciona 's' no final → tomate → tomates
        variantes.add(termo + "s")

    return list(variantes)
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
        if peso > 0:
            return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if match_g:
        peso = float(match_g.group(1).replace(',', '.')) / 1000
        if peso > 0:
            return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        if litros > 0:
            return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        if litros > 0:
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
        return f"R$ {preco_total:.2f}".replace('.', ',')
    unidade = unidade.lower()
    if quantidade and quantidade != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(quantidade).replace('.', ',')}{unidade.lower()}"
    else:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{unidade.lower()}"

# Funções para Shibata
def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        response = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if response.status_code == 200:
            data = response.json().get('data', {}).get('produtos', [])
            return [produto for produto in data if produto.get("disponivel", True)]
        else:
            st.error(f"Erro na busca do Shibata (página {pagina}): Status {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com Shibata (página {pagina}): {e}")
        return []
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a resposta do Shibata (página {pagina}): {e}")
        return []

# Funções para Nagumo
def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_nome = remover_acentos(nome.lower())
    texto_desc = remover_acentos(descricao.lower())

    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        rolos = int(match.group(1))
        folhas_por_rolo = int(match.group(3))
        total_folhas = rolos * folhas_por_rolo
        return rolos, folhas_por_rolo, total_folhas, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"

    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        total_folhas = int(match.group(1))
        return None, None, total_folhas, f"{total_folhas} {match.group(2)}"

    texto_completo = f"{texto_nome} {texto_desc}"

    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        rolos = int(match.group(1))
        folhas_por_rolo = int(match.group(3))
        total_folhas = rolos * folhas_por_rolo
        return rolos, folhas_por_rolo, total_folhas, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"

    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        total_folhas = int(match.group(1))
        return None, None, total_folhas, f"{total_folhas} {match.group(2)}"

    m_un = re.search(r"(\d+)\s*(un|unidades?)", texto_completo)
    if m_un:
        total = int(m_un.group(1))
        return None, None, total, f"{total} unidades"

    return None, None, None, None


def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    preco_unitario = "Sem unidade"
    texto_completo = f"{nome} {descricao}".lower()

    if contem_papel_toalha(texto_completo):
        rolos, folhas_por_rolo, total_folhas, texto_exibicao = extrair_info_papel_toalha(nome, descricao)
        if total_folhas and total_folhas > 0:
            preco_por_item = preco_valor / total_folhas
            return f"R$ {preco_por_item:.3f}/folha"
        return "Preço por folha: n/d"

    if "papel higi" in texto_completo:
        match_rolos = re.search(r"leve\s*0*(\d+)|c/\s*0*(\d+)|(\d+)\s*rolos?|(\d+)\s*(un|unidades?)", texto_completo)
        match_metros = re.search(r"(\d+[.,]?\d*)\s*(m|metros?|mt)", texto_completo)
        if match_rolos and match_metros:
            try:
                rolos = int(next(g for g in match_rolos.groups() if g is not None))
                metros = float(match_metros.group(1).replace(',', '.'))
                if rolos > 0 and metros > 0:
                    preco_por_metro = preco_valor / rolos / metros
                    return f"R$ {preco_por_metro:.3f}/m"
            except (ValueError, ZeroDivisionError, StopIteration):
                pass

    fontes = [descricao.lower(), nome.lower()]
    for fonte in fontes:
        match_g = re.search(r"(\d+[.,]?\d*)\s*(g|gramas?)", fonte)
        if match_g:
            gramas = float(match_g.group(1).replace(',', '.'))
            if gramas > 0:
                return f"R$ {preco_valor / (gramas / 1000):.2f}/kg"
        match_kg = re.search(r"(\d+[.,]?\d*)\s*(kg|quilo)", fonte)
        if match_kg:
            kg = float(match_kg.group(1).replace(',', '.'))
            if kg > 0:
                return f"R$ {preco_valor / kg:.2f}/kg"
        match_ml = re.search(r"(\d+[.,]?\d*)\s*(ml|mililitros?)", fonte)
        if match_ml:
            ml = float(match_ml.group(1).replace(',', '.'))
            if ml > 0:
                return f"R$ {preco_valor / (ml / 1000):.2f}/L"
        match_l = re.search(r"(\d+[.,]?\d*)\s*(l|litros?)", fonte)
        if match_l:
            litros = float(match_l.group(1).replace(',', '.'))
            if litros > 0:
                return f"R$ {preco_valor / litros:.2f}/L"
        match_un = re.search(r"(\d+[.,]?\d*)\s*(un|unidades?)", fonte)
        if match_un:
            unidades = float(match_un.group(1).replace(',', '.'))
            if unidades > 0:
                return f"R$ {preco_valor / unidades:.2f}/un"

    if unidade_api:
        unidade_api = unidade_api.lower()
        if unidade_api == 'kg':
            return f"R$ {preco_valor:.2f}/kg"
        elif unidade_api == 'g':
            return f"R$ {preco_valor * 1000:.2f}/kg"
        elif unidade_api == 'l':
            return f"R$ {preco_valor:.2f}/L"
        elif unidade_api == 'ml':
            return f"R$ {preco_valor * 1000:.2f}/L"
        elif unidade_api == 'un':
            return f"R$ {preco_valor:.2f}/un"

    return preco_unitario

def extrair_valor_unitario(preco_unitario):
    match = re.search(r"R\$ (\d+[.,]?\d*)", preco_unitario)
    if match:
        return float(match.group(1).replace(',', '.'))
    return float('inf')

def buscar_nagumo(term="banana"):
    url = "https://nextgentheadless.instaleap.io/api/v3"
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.nagumo.com",
        "Referer": "https://www.nagumo.com/",
        "User-Agent": "Mozilla/5.0",
        "apollographql-client-name": "Ecommerce SSR",
        "apollographql-client-version": "0.11.0"
    }
    payload = {
        "operationName": "SearchProducts",
        "variables": {
            "searchProductsInput": {
                "clientId": "NAGUMO",
                "storeReference": "22",
                "currentPage": 1,
                "minScore": 1,
                "pageSize": 100,
                "search": [{"query": term}],
                "sort": 2,  # <-- CORREÇÃO APLICADA AQUI
                "filters": {},
                "googleAnalyticsSessionId": ""
            }
        },
        "query": """
        query SearchProducts($searchProductsInput: SearchProductsInput!) {
          searchProducts(searchProductsInput: $searchProductsInput) {
            products {
              name
              price
              photosUrl
              sku
              stock
              description
              unit
              promotion {
                isActive
                type
                conditions {
                  price
                  priceBeforeTaxes
                }
              }
            }
          }
        }
        """
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("searchProducts", {}).get("products", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com Nagumo: {e}")
        return []
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar a resposta do Nagumo: {e}")
        return []

# Configuração da página
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div, span, strong, small { font-size: 0.75rem !important; }
        img { max-width: 100px; height: auto; }
        .product-container {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .product-image {
            min-width: 80px;
            max-width: 80px;
            flex-shrink: 0;
        }
        .product-image img {
            border-radius: 8px;
        }
        .product-info {
            flex: 1 1 auto;
            min-width: 0;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        hr.product-separator {
            border: none;
            border-top: 1px solid #eee;
            margin: 10px 0;
        }
        .info-cinza {
            color: gray;
            font-size: 0.8rem;
        }
        [data-testid="stColumn"] {
            overflow-y: auto;
            max-height: 90vh;
            padding: 10px;
            border: 1px solid #f0f2f6;
            border-radius: 8px;
            max-width: 480px;
            margin-left: auto;
            margin-right: auto;
            background: transparent;
            scrollbar-width: thin;
            scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar {
            width: 6px;
            background: transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar-track {
            background: transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb {
            background-color: gray;
            border-radius: 3px;
            border: 1px solid transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb:hover {
            background-color: white;
        }
        .block-container {
            padding-right: 47px !important;
        }
        input[type="text"] {
            font-size: 0.8rem !important;
        }
        .block-container {
            padding-bottom: 15px !important;
            margin-bottom: 15px !important;
        }
        [data-testid="stColumn"] {
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)

termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip().lower()

if termo:
    termos_expandidos = gerar_formas_variantes(remover_acentos(termo))
    col1, col2 = st.columns(2)

    with st.spinner("🔍 Buscando produtos..."):
        # Shibata
        produtos_shibata = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(buscar_pagina_shibata, t, pagina) for t in termos_expandidos for pagina in range(1, 11)}
            for future in as_completed(futures):
                produtos_shibata.extend(future.result())

        ids_vistos = set()
        produtos_shibata_unicos = [p for p in produtos_shibata if p.get('id') not in ids_vistos and not ids_vistos.add(p.get('id'))]

        termo_sem_acento = remover_acentos(termo)
        palavras_termo = termo_sem_acento.split()
        produtos_shibata_filtrados = [p for p in produtos_shibata_unicos if all(palavra in remover_acentos(f"{p.get('descricao', '')} {p.get('nome', '')}") for palavra in palavras_termo)]

        produtos_shibata_processados = []
        for p in produtos_shibata_filtrados:
            preco = float(p.get('preco') or 0)
            em_oferta = p.get('em_oferta', False)
            oferta_info = p.get('oferta') or {}
            preco_oferta = oferta_info.get('preco_oferta')
            preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco
            descricao = p.get('descricao', '')
            
            p['preco_unidade_val'] = float('inf')
            if 'papel higienico' in termo_sem_acento:
                preco_val, _ = calcular_precos_papel(descricao, preco_total)
                if preco_val: p['preco_unidade_val'] = preco_val
            elif 'papel toalha' in termo_sem_acento:
                _, preco_val = calcular_preco_papel_toalha(descricao, preco_total)
                if preco_val: p['preco_unidade_val'] = preco_val
            else:
                preco_val, _ = calcular_preco_unidade(descricao, preco_total)
                if preco_val: p['preco_unidade_val'] = preco_val
            
            produtos_shibata_processados.append(p)

        produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=lambda x: x['preco_unidade_val'])

        # Nagumo
        produtos_nagumo = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(buscar_nagumo, t) for t in termos_expandidos}
            for future in as_completed(futures):
                produtos_nagumo.extend(future.result())

        produtos_nagumo_unicos = {p['sku']: p for p in produtos_nagumo}.values()
        produtos_nagumo_filtrados = [p for p in produtos_nagumo_unicos if all(palavra in remover_acentos(f"{p['name']} {p.get('description', '')}") for palavra in palavras_termo)]

        for p in produtos_nagumo_filtrados:
            preco_normal = p.get("price", 0)
            promocao = p.get("promotion") or {}
            cond = promocao.get("conditions") or []
            preco_desconto = cond[0].get("price") if promocao.get("isActive") and cond else None
            preco_exibir = preco_desconto if preco_desconto else preco_normal
            
            p['preco_unitario_str'] = calcular_preco_unitario_nagumo(preco_exibir, p['description'], p['name'], p.get("unit"))
            p['preco_unitario_valor'] = extrair_valor_unitario(p['preco_unitario_str'])
            
            titulo = p['name']
            if contem_papel_toalha(f"{p['name']} {p['description']}"):
                _, _, _, texto_exibicao = extrair_info_papel_toalha(p['name'], p['description'])
                if texto_exibicao:
                    titulo += f" <span class='info-cinza'>({texto_exibicao})</span>"
            if "papel higi" in remover_acentos(titulo.lower()):
                titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
            p['titulo_exibido'] = titulo

        produtos_nagumo_ordenados = sorted(produtos_nagumo_filtrados, key=lambda x: x['preco_unitario_valor'])

    # Exibição Shibata
    with col1:
        st.markdown(f'''<h5 style="display: flex; align-items: center; justify-content: center;"><img src="https://raw.githubusercontent.com/gymbr/precosmercados/refs/heads/main/logo-shibata.png" width="80" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>Shibata</h5>''', unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(produtos_shibata_ordenados)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        if not produtos_shibata_ordenados:
            st.warning("Nenhum produto encontrado.")
        for p in produtos_shibata_ordenados:
            preco = float(p.get('preco') or 0)
            em_oferta = p.get('em_oferta', False)
            oferta_info = p.get('oferta') or {}
            preco_oferta = oferta_info.get('preco_oferta')
            preco_antigo = oferta_info.get('preco_antigo')
            preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco
            
            preco_html = ""
            if em_oferta and preco_oferta and preco_antigo:
                desconto = round(100 * (float(preco_antigo) - float(preco_oferta)) / float(preco_antigo))
                preco_html = f"<div><b>R$ {float(preco_oferta):.2f}</b> <span style='color:red;font-weight: bold;'>({desconto}% OFF)</span></div><div><span style='color:gray; text-decoration: line-through;'>R$ {float(preco_antigo):.2f}</span></div>"
            else:
                preco_html = f"<div><b>R$ {preco_total:.2f}</b></div>"

            descricao_modificada = p.get('descricao', '')
            preco_info_extra = ""
            if 'papel higienico' in termo_sem_acento:
                _, preco_por_metro_str = calcular_precos_papel(descricao_modificada, preco_total)
                if preco_por_metro_str: preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>{preco_por_metro_str}</div>"
                descricao_modificada = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
                descricao_modificada = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
            elif 'papel toalha' in termo_sem_acento:
                total_folhas, preco_por_folha = calcular_preco_papel_toalha(descricao_modificada, preco_total)
                if total_folhas and preco_por_folha:
                    descricao_modificada += f" <span style='color:gray;'>({total_folhas} folhas)</span>"
                    preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_folha:.3f}/folha</div>"
            else:
                _, preco_por_unidade_str = calcular_preco_unidade(descricao_modificada, preco_total)
                if preco_por_unidade_str: preco_info_extra = f"<div style='color:gray; font-size:0.75em;'>{preco_por_unidade_str}</div>"

            st.markdown(f"""
                <div class='product-container'>
                    <div class='product-image'><img src='https://produtos.vipcommerce.com.br/250x250/{p.get("imagem", "")}'/></div>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'><b>{descricao_modificada}</b></div>
                        {preco_html}
                        {preco_info_extra}
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # Exibição Nagumo
    with col2:
        st.markdown(f'''<h5 style="display: flex; align-items: center; justify-content: center;"><img src="https://raw.githubusercontent.com/gymbr/precosmercados/refs/heads/main/logo-nagumo.png" width="80" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 2px;"/>Nagumo</h5>''', unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(produtos_nagumo_ordenados)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        if not produtos_nagumo_ordenados:
            st.warning("Nenhum produto encontrado.")
        for p in produtos_nagumo_ordenados:
            preco_normal = p['price']
            promocao = p.get("promotion") or {}
            cond = promocao.get("conditions") or []
            preco_desconto = cond[0].get("price") if promocao.get("isActive") and cond else None
            
            preco_html = ""
            if preco_desconto and preco_desconto < preco_normal:
                desconto_percentual = ((preco_normal - preco_desconto) / preco_normal) * 100
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_desconto:.2f}</span> <span style='color: red; font-weight: bold;'> ({desconto_percentual:.0f}% OFF)</span><br><span style='text-decoration: line-through; color: gray;'>R$ {preco_normal:.2f}</span>"
            else:
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_normal:.2f}</span>"
            
            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <div style="flex: 0 0 auto;"><img src="{p['photosUrl'][0] if p.get('photosUrl') else ''}" width="80" style="border-radius:8px;"/></div>
                    <div style="flex: 1; word-break: break-word; overflow-wrap: anywhere;">
                        <strong>{p['titulo_exibido']}</strong><br>
                        {preco_html}<br>
                        <div style="margin-top: 4px; font-size: 0.9em; color: #666;">{p['preco_unitario_str']}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)
