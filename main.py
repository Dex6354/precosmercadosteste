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

    # ⚠️ Nova lógica para 'leve X pague Y folhas' → usa o número após 'leve'
    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        preco_por_folha = preco_total / folhas_leve if folhas_leve else None
        return folhas_leve, preco_por_folha

    # Lógica alternativa caso não tenha o padrão acima
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

    # Prioritize name for unit information
    # Pattern 1: X Un Y Folhas (e.g., "Papel Toalha Kitchen Com 2Un 60 Folhas")
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        rolos = int(match.group(1))
        folhas_por_rolo = int(match.group(3))
        total_folhas = rolos * folhas_por_rolo
        return rolos, folhas_por_rolo, total_folhas, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"

    # Pattern 2: X Folhas (e.g., "Papel Toalha 200 Folhas")
    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_nome)
    if match:
        total_folhas = int(match.group(1))
        return None, None, total_folhas, f"{total_folhas} {match.group(2)}"

    # If not in name, try description with the same priority
    texto_completo = f"{texto_nome} {texto_desc}" # Combine for broader search if not found in name

    # Pattern 1 (from description): X Un Y Folhas
    match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        rolos = int(match.group(1))
        folhas_por_rolo = int(match.group(3))
        total_folhas = rolos * folhas_por_rolo
        return rolos, folhas_por_rolo, total_folhas, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"

    # Pattern 2 (from description): X Folhas
    match = re.search(r'(\d+)\s*(folhas|toalhas)', texto_completo)
    if match:
        total_folhas = int(match.group(1))
        return None, None, total_folhas, f"{total_folhas} {match.group(2)}"

    # Pattern 3: X Unidades (general unit, less specific for paper towels)
    m_un = re.search(r"(\d+)\s*(un|unidades?)", texto_completo)
    if m_un:
        total = int(m_un.group(1))
        return None, None, total, f"{total} unidades"

    return None, None, None, None


def calcular_preco_unitario_nagumo(preco_valor, descricao, nome, unidade_api=None):
    preco_unitario = "Sem unidade"
    texto_completo = f"{nome} {descricao}".lower() # Combine name and description for unit extraction

    if contem_papel_toalha(texto_completo):
        rolos, folhas_por_rolo, total_folhas, texto_exibicao = extrair_info_papel_toalha(nome, descricao)
        if total_folhas and total_folhas > 0:
            preco_por_item = preco_valor / total_folhas
            return f"R$ {preco_por_item:.3f}/folha"
        return "Preço por folha: n/d"

    if "papel higi" in texto_completo:
        match_rolos = re.search(r"leve\s*0*(\d+)", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"\blv?\s*0*(\d+)", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"\blv?(\d+)", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"\bl\s*0*(\d+)", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"c/\s*0*(\d+)", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"(\d+)\s*rolos?", texto_completo)
        if not match_rolos:
            match_rolos = re.search(r"(\d+)\s*(un|unidades?)", texto_completo)
        match_metros = re.search(r"(\d+[.,]?\d*)\s*(m|metros?|mt)", texto_completo)
        if match_rolos and match_metros:
            try:
                rolos = int(match_rolos.group(1))
                metros = float(match_metros.group(1).replace(',', '.'))
                if rolos > 0 and metros > 0:
                    preco_por_metro = preco_valor / rolos / metros
                    return f"R$ {preco_por_metro:.3f}/m"
            except:
                pass

    # General unit extraction (for other products)
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
                "pageSize": 500,
                "search": [{"query": term}],
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
    min-width: 0; /* 👈 ESSENCIAL para permitir quebra */
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
        /* Estilos para barra de rolagem data-testid="stColumn" (inicio) */


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
    scrollbar-color: gray transparent;  /* Firefox: thumb branco, track transparente */
}

/* WebKit (Chrome, Safari, Edge) */
[data-testid="stColumn"]::-webkit-scrollbar {
    width: 6px;
    background: transparent;
}

[data-testid="stColumn"]::-webkit-scrollbar-track {
    background: transparent; /* fundo transparente */
}

[data-testid="stColumn"]::-webkit-scrollbar-thumb {
    background-color: gray; /* barrinha branca translúcida */
    border-radius: 3px;
    border: 1px solid transparent;
}

[data-testid="stColumn"]::-webkit-scrollbar-thumb:hover {
    background-color: white; /* barrinha mais visível ao passar o mouse */
}

/* Estilos para barra de rolagem data-testid="stColumn" (fim) */

.block-container {
    padding-right: 47px !important;  /* Tamanho do espaco para rolagem */
}

        /* Reduz o tamanho da fonte da caixa de pesquisa */
input[type="text"] {
    font-size: 0.8rem !important;
}
/* Tamanho do espaco no final da pagina */
.block-container {
    padding-bottom: 15px !important;
    margin-bottom: 15px !important;
}
/* Tamanho do espaco entre colunas */
[data-testid="stColumn"] {
margin-bottom: 20px;
}
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)

termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip().lower()

# Expansão automática (singular/plural)
termos_expandidos = gerar_formas_variantes(remover_acentos(termo))

if termo:
    # Cria as duas colunas principais
    col1, col2 = st.columns(2)

    with st.spinner("🔍 Buscando produtos..."):
        # Processa e busca Shibata
        produtos_shibata = []
        max_workers = 8
        max_paginas = 15
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(buscar_pagina_shibata, t, pagina)
                           for t in termos_expandidos
                           for pagina in range(1, max_paginas + 1)]
            for future in as_completed(futures):
                    produtos_shibata.extend(future.result())

        # Remover duplicados por ID
        ids_vistos = set()
        produtos_shibata = [p for p in produtos_shibata if p.get('id') not in ids_vistos and not ids_vistos.add(p.get('id'))]


        termo_sem_acento = remover_acentos(termo)
        palavras_termo = termo_sem_acento.split()
        produtos_shibata_filtrados = [
            p for p in produtos_shibata
            if all(
                palavra in remover_acentos(
                    f"{p.get('descricao', '')} {p.get('nome', '')}"
                ) for palavra in palavras_termo
            )
        ]



        produtos_shibata_processados = []
        for p in produtos_shibata_filtrados:
            if not p.get("disponivel", True):
                continue
            preco = float(p.get('preco') or 0)
            em_oferta = p.get('em_oferta', False)
            oferta_info = p.get('oferta') or {}
            preco_oferta = oferta_info.get('preco_oferta')
            preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco
            descricao = p.get('descricao', '')
            quantidade_dif = p.get('quantidade_unidade_diferente')
            unidade_sigla = p.get('unidade_sigla')
            # Ignorar "grande" na unidade
            if unidade_sigla and unidade_sigla.lower() == "grande":
                unidade_sigla = None
            preco_unidade_str = formatar_preco_unidade_personalizado(preco_total, quantidade_dif, unidade_sigla)
            descricao_limpa = descricao.lower().replace('grande', '').strip()
            preco_unidade_val, _ = calcular_preco_unidade(descricao_limpa, preco_total)

            # 🧠 NOVO: tenta extrair unidade direto do preço formatado (ex: /0,15kg → calcula R$/kg)
            match = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml)", preco_unidade_str.lower())
            if match:
                try:
                    quantidade = float(match.group(1).replace(",", "."))
                    unidade = match.group(2).lower()
                    if unidade == "g":
                        quantidade /= 1000
                        unidade = "kg"
                    elif unidade == "ml":
                        quantidade /= 1000
                        unidade = "l"
                    if quantidade > 0:
                        preco_unidade_val = preco_total / quantidade
                        preco_unidade_str += f"<br><span style='color:gray;'>R$ {preco_unidade_val:.2f}/{unidade}</span>"
                except:
                    pass



            preco_por_metro_val, _ = calcular_precos_papel(descricao, preco_total)

            # Se não foi possível calcular preço por unidade (como kg, L), apenas repete a unidade do preço
            if not preco_unidade_val or preco_unidade_val == float('inf'):
                # Tenta extrair unidade do preço formatado original
                match_unidade = re.search(r"/\s*([a-zA-Z]+)", preco_unidade_str.lower())
                unidade_fallback = match_unidade.group(1) if match_unidade else "un"
                preco_unidade_val = preco_total
                preco_unidade_str += f"<br><span style='color:gray;'>R$ {preco_total:.2f}/{unidade_fallback}</span>"

            # Atualiza os campos usados na ordenação e exibição
            p['preco_unidade_val'] = preco_unidade_val
            p['preco_unidade_str'] = preco_unidade_str

            p['preco_por_metro_val'] = preco_por_metro_val if preco_por_metro_val else float('inf')
            produtos_shibata_processados.append(p)

        if 'papel toalha' in termo_sem_acento:
            for p in produtos_shibata_processados:
                preco_oferta = (p.get('oferta') or {}).get('preco_oferta')
                preco_atual = float(preco_oferta) if preco_oferta else float(p.get('preco') or 0)
                total_folhas, preco_por_folha = calcular_preco_papel_toalha(p.get('descricao', ''), preco_atual)
                p['preco_por_folha_val'] = preco_por_folha if preco_por_folha else float('inf')
            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=lambda x: x['preco_por_folha_val'])
        elif 'papel higienico' in termo_sem_acento:
            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=lambda x: x['preco_por_metro_val'])
        else:
            def preco_mais_preciso(produto):
                descricao = produto.get('descricao', '').lower()
                preco = float(produto.get('preco') or 0)
                oferta = produto.get('oferta') or {}
                preco_oferta = oferta.get('preco_oferta')
                em_oferta = produto.get('em_oferta', False)
                preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco

                # 🥚 Prioridade especial para ovo ou dúzia
                if 'ovo' in remover_acentos(descricao):
                    match_duzia = re.search(r'1\s*d[uú]zia', descricao)
                    if match_duzia:
                        return preco_total / 12
                    match = re.search(r'(\d+)\s*(unidades|un|ovos|c\/|c\d+|com)', descricao)
                    if match:
                        qtd = int(match.group(1))
                        if qtd > 0:
                            return preco_total / qtd

                # Normal: unidade/kg/L se disponível
                valores = []

                unidade = produto.get('preco_unidade_val')
                litro = produto.get('preco_por_litro_val')  # se implementado
                peso = produto.get('preco_por_kg_val')      # se implementado

                if unidade and unidade != float('inf'):
                    valores.append(unidade)
                if litro and litro != float('inf'):
                    valores.append(litro)
                if peso and peso != float('inf'):
                    valores.append(peso)

                if valores:
                    return min(valores)

                return float('inf')



            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=preco_mais_preciso)


        # Processa e busca Nagumo
        produtos_nagumo = []

        # Adiciona cada termo expandido à busca
        for termo_expandido in termos_expandidos:
            produtos_nagumo.extend(buscar_nagumo(termo_expandido))

        for palavra in palavras_termo:
            produtos_nagumo.extend(buscar_nagumo(palavra))

        produtos_nagumo_unicos = {p['sku']: p for p in produtos_nagumo}.values()

        produtos_nagumo_filtrados = []
        for produto in produtos_nagumo_unicos:
            texto = f"{produto['name']} {produto.get('description', '')}"
            texto_normalizado = remover_acentos(texto)
            if all(p in texto_normalizado for p in palavras_termo):
                produtos_nagumo_filtrados.append(produto)

        for p in produtos_nagumo_filtrados:
            preco_normal = p.get("price", 0)
            promocao = p.get("promotion") or {}
            cond = promocao.get("conditions") or []
            preco_desconto = None
            if promocao.get("isActive") and isinstance(cond, list) and len(cond) > 0:
                preco_desconto = cond[0].get("price")
            preco_exibir = preco_desconto if preco_desconto else preco_normal

            p['preco_unitario_str'] = calcular_preco_unitario_nagumo(preco_exibir, p['description'], p['name'], p.get("unit"))
            p['preco_unitario_valor'] = extrair_valor_unitario(p['preco_unitario_str'])

            titulo = p['name']
            texto_completo = p['name'] + " " + p['description']
            if contem_papel_toalha(texto_completo):
                rolos, folhas_por_rolo, total_folhas, texto_exibicao = extrair_info_papel_toalha(p['name'], p['description'])
                if texto_exibicao:
                    titulo += f" <span class='info-cinza'>({texto_exibicao})</span>"
            if "papel higi" in remover_acentos(titulo.lower()):
                titulo_lower = remover_acentos(titulo.lower())
                if "folha simples" in titulo_lower:
                    titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                if "folha dupla" in titulo_lower or "folha tripla" in titulo_lower:
                    titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
            p['titulo_exibido'] = titulo

        produtos_nagumo_ordenados = sorted(produtos_nagumo_filtrados, key=lambda x: x['preco_unitario_valor'])

    # Exibição dos resultados na COLUNA 1 (Shibata)
            # Exibição dos resultados na COLUNA 1 (Shibata)
        with col1:
                    st.markdown(f"""
                        <h5 style="display: flex; align-items: center; justify-content: center;">
                        <img src="https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png" width="80" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
                        Shibata
                        </h5>
                    """, unsafe_allow_html=True)
                    st.markdown(f"<small>🔎 {len(produtos_shibata_ordenados)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)

                    if not produtos_shibata_ordenados:
                        st.warning("Nenhum produto encontrado.")

                    for p in produtos_shibata_ordenados:
                        preco = float(p.get('preco') or 0)
                        descricao = p.get('descricao', '')
                        imagem = p.get('imagem', '')
                        em_oferta = p.get('em_oferta', False)
                        oferta_info = p.get('oferta') or {}
                        preco_oferta = oferta_info.get('preco_oferta')
                        preco_antigo = oferta_info.get('preco_antigo')
                        imagem_url = f"https://produtos.vipcommerce.com.br/250x250/{imagem}"
                        preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco
                        quantidade_dif = p.get('quantidade_unidade_diferente')
                        unidade_sigla = p.get('unidade_sigla')
                        preco_formatado = formatar_preco_unidade_personalizado(preco_total, quantidade_dif, unidade_sigla)

                        preco_info_extra = ""
                        descricao_modificada = descricao

                        # Cálculo extraído de preco_formatado: /0,15kg ou /250ml
                        match_preco_unitario = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml)", preco_formatado.lower())
                        if match_preco_unitario:
                            quantidade_str = match_preco_unitario.group(1).replace(",", ".")
                            unidade = match_preco_unitario.group(2)

                            try:
                                quantidade = float(quantidade_str)
                                if unidade == "g":
                                    quantidade /= 1000
                                    unidade = "kg"
                                elif unidade == "ml":
                                    quantidade /= 1000
                                    unidade = "l"

                                if quantidade > 0:
                                    preco_unitario = preco_total / quantidade
                                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_unitario:.2f}/{unidade}</div>"
                            except:
                                pass

                        # Destaques para papel higiênico
                        if 'papel higienico' in remover_acentos(descricao):
                            descricao_modificada = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
                            descricao_modificada = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)

                        # Preço por folha (papel toalha)
                        total_folhas, preco_por_folha = calcular_preco_papel_toalha(descricao, preco_total)
                        if total_folhas and preco_por_folha:
                            descricao_modificada += f" <span style='color:gray;'>({total_folhas} folhas)</span>"
                            preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_folha:.3f}/folha</div>"
                        else:
                            _, preco_por_metro_str = calcular_precos_papel(descricao, preco_total)
                            _, preco_por_unidade_str = calcular_preco_unidade(descricao, preco_total)
                            if preco_por_metro_str:
                                preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_metro_str}</div>"
                            # Evitar mostrar preço por unidade baseado na descrição se a unidade já está presente no preço_formatado
                            # Se já há unidade válida no preço formatado, evita duplicar info do título
                            match_preco_formatado = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml|un|l|ml|folhas?|m)", preco_formatado.lower())
                            unidade_presente_no_preco = bool(match_preco_formatado)
                            if not unidade_presente_no_preco:

                                _, preco_por_unidade_str = calcular_preco_unidade(descricao, preco_total)
                                if preco_por_unidade_str:
                                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_unidade_str}</div>"


                        # Preço por unidade (ovo)
                        if 'ovo' in remover_acentos(descricao).lower():
                            match_ovo = re.search(r'(\d+)\s*(unidades|un|ovos|c/|com)', descricao.lower())
                            if match_ovo:
                                qtd_ovos = int(match_ovo.group(1))
                                if qtd_ovos > 0:
                                    preco_por_ovo = preco_total / qtd_ovos
                                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_ovo:.2f}/unidade</div>"

                        if re.search(r'1\s*d[uú]zia', descricao.lower()):
                            preco_por_unidade_duzia = preco_total / 12
                            preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_unidade_duzia:.2f}/unidade (dúzia)</div>"

                        # Preço (com ou sem oferta)
                        if em_oferta and preco_oferta and preco_antigo:
                            preco_oferta_val = float(preco_oferta)
                            preco_antigo_val = float(preco_antigo)
                            desconto = round(100 * (preco_antigo_val - preco_oferta_val) / preco_antigo_val) if preco_antigo_val else 0
                            preco_antigo_str = f"R$ {preco_antigo_val:.2f}".replace('.', ',')
                            preco_html = f"""
                                <div><b>{preco_formatado}</b><br> <span style='color:red;font-weight: bold;'>({desconto}% OFF)</span></div>
                                <div><span style='color:gray; text-decoration: line-through;'>{preco_antigo_str}</span></div>
                            """
                        else:
                            preco_html = f"<div><b>{preco_formatado}</b></div>"

                        # Renderização final do produto
                        st.markdown(f"""
                            <div class='product-container'>
                                <div class='product-image'>
                                    <img src='{imagem_url}' width='80' style='display: block;'/>
                                    <img src='https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png' width='80' 
                                        style='background-color: white; display: block; margin: 0 auto; border-radius: 4px; padding: 3px;'/>
                                </div>
                                <div class='product-info'>
                                    <div style='margin-bottom: 4px;'><b>{descricao_modificada}</b></div>
                                    <div style='font-size:0.85em;'>{preco_html}</div>
                                    <div style='font-size:0.85em;'>{preco_info_extra}</div>
                                </div>
                            </div>
                            <hr class='product-separator' />
                        """, unsafe_allow_html=True)


    # Exibição dos resultados na COLUNA 2 (Nagumo)
    with col2:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,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rgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQADEFQAAAAAAgACIKwAAAAAAAAEQVwAAAAAAAAIgrgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQADEFQAAAAAAgACIKwAAAAAAAAEQVwAAAAAAAAIgrgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQAD/H9nzpH/1Exb4AAAAAElFTkSuQmCC" width="80" style="margin-right:8px; border-radius: 6px; padding: 0px;"/>
                Nagumo
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(produtos_nagumo_ordenados)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        if not produtos_nagumo_ordenados:
            st.warning("Nenhum produto encontrado.")
        for p in produtos_nagumo_ordenados:
            imagem = p['photosUrl'][0] if p.get('photosUrl') else ""
            preco_unitario = p['preco_unitario_str']
            preco = p['price']
            promocao = p.get("promotion") or {}
            cond = promocao.get("conditions") or []
            preco_desconto = None
            if promocao.get("isActive") and isinstance(cond, list) and len(cond) > 0:
                preco_desconto = cond[0].get("price")
            if preco_desconto and preco_desconto < preco:
                desconto_percentual = ((preco - preco_desconto) / preco) * 100
                preco_html = f"""
                    <span style='font-weight: bold; font-size: 1rem;'>R$ {preco_desconto:.2f}</span><br>
                    <span style='color: red; font-weight: bold;'> ({desconto_percentual:.0f}% OFF)</span><br>
                    <span style='text-decoration: line-through; color: gray;'>R$ {preco:.2f}</span>
                """
            else:
                preco_html = f"R$ {preco:.2f}"
            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <div style="flex: 0 0 auto;">
                        <img src="{imagem}" width="80" style="border-radius:8px; display: block;"/>
                        <img src="data:image/png;base64,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rgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQADEFQAAAAAAgACIKwAAAAAAAAEQVwAAAAAAAAIgrgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQADEFQAAAAAAgACIKwAAAAAAAAEQVwAAAAAAAAIgrgAAAAAAAARAXAEAAAAAAAiAuAIAAAAAABAAcQUAAAAAACAA4goAAAAAAEAAxBUAAAAAAIAAiCsAAAAAAAABEFcAAAAAAAACIK4AAAAAAAAEQFwBAAAAAAAIgLgCAAAAAAAQAHEFAAAAAAAgAOIKAAAAAABAAMQVAAAAAACAAIgrAAAAAAAAARBXAAAAAAAAAiCuAAAAAAAABEBcAQAAAAAACIC4AgAAAAAAEABxBQAAAAAAIADiCgAAAAAAQAD/H9nzpH/1Exb4AAAAAElFTkSuQmCC" width="80" style="border-radius: 6px; padding: 0px; display: block;"/>
</div>
                    <div style="flex: 1; word-break: break-word; overflow-wrap: anywhere;">
                        <strong>{p['titulo_exibido']}</strong><br>
                        <strong>{preco_html}</strong><br>
                        <div style="margin-top: 4px; font-size: 0.9em; color: #666;">{preco_unitario}</div>
                        <div style="color: gray; font-size: 0.8em;">Estoque: {p['stock']}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)
