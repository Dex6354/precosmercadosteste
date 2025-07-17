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
                "pageSize": 100,
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
                        <img src="https://raw.githubusercontent.com/Dex6354/PrecoShibata/refs/heads/main/logo-shibata.png" width="80" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
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
                                    <img src='https://raw.githubusercontent.com/Dex6354/PrecoShibata/refs/heads/main/logo-shibata.png' width='80' 
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
                <img src="https://institucional.nagumo.com.br/images/nagumo-2000.png" width="80" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 2px;"/>
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
                        <img src="https://institucional.nagumo.com.br/images/nagumo-2000.png" width="80" style="background-color: white; border-radius: 4px; padding: 3px; display: block;"/>
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
