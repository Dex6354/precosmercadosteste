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
        # Remove o 's' final → banana**s** → banana
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

# Funções para Nagumo (LÓGICA ATUALIZADA DO CÓDIGO NOVO)
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
header[data-testid="stHeader"] {
    display: none;
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
            
            # --- Criação da URL do Shibata ---
            produto_id = p.get('produto_id') 
            produto_nome_url = slugify(p.get('descricao', p.get('nome', 'produto')))
            if produto_id:
                p['url_shibata'] = f"https://www.loja.shibata.com.br/produto/{produto_id}/{produto_nome_url}"
            else:
                p['url_shibata'] = "https://www.loja.shibata.com.br/" # Fallback
            
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
                        preco_unitario = preco_total / quantidade
                        preco_unidade_str += f"<br><span style='color:gray;'>R$ {preco_unitario:.2f}/{unidade}</span>"
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

                valores = []
                unidade = produto.get('preco_unidade_val')
                if unidade and unidade != float('inf'):
                    valores.append(unidade)

                if valores:
                    return min(valores)
                return float('inf')

            produtos_shibata_ordenados = sorted(produtos_shibata_processados, key=preco_mais_preciso)

        # --- PROCESSAMENTO NAGUMO (LÓGICA ATUALIZADA DO CÓDIGO NOVO) ---
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
                    
                    # URL atualizada
                    p['url_final'] = f"https://www.nagumo.com.br/categoria/departamentos/p/{slugify(nome)}-{sku}.html"
                    
                    label, sort_v = calc_unitario_nagumo(preco_final, desc, nome, p.get('unit'))
                    p['unit_label'] = label
                    p['sort_val'] = sort_v
                    p['preco_final'] = preco_final
                    nagumo_final.append(p)
        produtos_nagumo_ordenados = sorted(nagumo_final, key=lambda x: x['sort_val'] or 999)

    # Exibição dos resultados na COLUNA 1 (Shibata)
    with col1:
                st.markdown(f"""
                    <h5 style="display: flex; align-items: center; justify-content: center;">
                    <img src="{LOGO_SHIBATA_URL}" width="80" alt="Shibata" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
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
                    url_produto = p.get('url_shibata', '#')

                    imagem_url = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{imagem}" if imagem else DEFAULT_IMAGE_URL
                    
                    preco_total = float(preco_oferta) if em_oferta and preco_oferta else preco
                    quantidade_dif = p.get('quantidade_unidade_diferente')
                    unidade_sigla = p.get('unidade_sigla')
                    preco_formatado = formatar_preco_unidade_personalizado(preco_total, quantidade_dif, unidade_sigla)

                    preco_info_extra = ""
                    descricao_modificada = descricao

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
                        except: pass

                    if 'papel higienico' in remover_acentos(descricao):
                        descricao_modificada = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
                        descricao_modificada = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)

                    total_folhas, preco_por_folha = calcular_preco_papel_toalha(descricao, preco_total)
                    if total_folhas and preco_por_folha:
                        descricao_modificada += f" <span style='color:gray;'>({total_folhas} folhas)</span>"
                        preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_folha:.3f}/folha</div>"
                    else:
                        _, preco_por_metro_str = calcular_precos_papel(descricao, preco_total)
                        if preco_por_metro_str:
                            preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_metro_str}</div>"
                        match_preco_formatado = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml|un|l|ml|folhas?|m)", preco_formatado.lower())
                        if not bool(match_preco_formatado):
                            _, preco_por_unidade_str = calcular_preco_unidade(descricao, preco_total)
                            if preco_por_unidade_str:
                                preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_unidade_str}</div>"

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

                    st.markdown(f"""
                        <div class='product-container'>
                            <a href='{url_produto}' target='_blank' class='product-image' style='text-decoration:none;'>
                                <img src='{imagem_url}' width='80' style='background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;'/>
                                <img src='{LOGO_SHIBATA_URL}' width='80' 
                                    style='background-color: white; display: block; margin: 0 auto; border-top: 1.5px solid black; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; padding: 3px;'/>
                            </a>
                            <div class='product-info'>
                                <div style='margin-bottom: 4px;'><a href='{url_produto}' target='_blank' style='text-decoration:none; color:inherit;'><b>{descricao_modificada}</b></a></div>
                                <div style='font-size:0.85em;'>{preco_html}</div>
                                <div style='font-size:0.85em;'>{preco_info_extra}</div>
                            </div>
                        </div>
                        <hr class='product-separator' />
                    """, unsafe_allow_html=True)


    # Exibição dos resultados na COLUNA 2 (Nagumo com LOGICA NOVA)
    with col2:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
                <img src="{LOGO_NAGUMO_URL}" width="80" alt="Nagumo" style="margin-right:8px; border-radius: 6px; border: 1.5px solid white; padding: 0px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(produtos_nagumo_ordenados)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        if not produtos_nagumo_ordenados:
            st.warning("Nenhum produto encontrado.")
        for p in produtos_nagumo_ordenados:
            imgs = p.get('photosUrl')
            imagem = imgs[0] if (isinstance(imgs, list) and imgs) else DEFAULT_IMAGE_URL
            url_produto = p['url_final']

            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <a href='{url_produto}' target='_blank' style='flex: 0 0 auto; text-decoration:none;'>
                        <img src="{imagem}" width="80" style="background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;"/>
                        <img src="{LOGO_NAGUMO_URL}" width="80" style="border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; border: 1.5px solid white; padding: 0px; display: block;"/>
                    </a>
                    <div style="flex: 1; word-break: break-word; overflow-wrap: anywhere;">
                        <a href='{url_produto}' target='_blank' style='text-decoration:none; color:inherit;'><strong>{p['name']}</strong></a><br>
                        <strong><span style='font-weight: bold; font-size: 1rem;'>R$ {p['preco_final']:.2f}</span></strong><br>
                        <div style="margin-top: 4px; font-size: 0.9em; color: #666;">{p['unit_label']}</div>
                        <div style="color: gray; font-size: 0.8em;">Estoque: {p.get('stock', 0)}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)
