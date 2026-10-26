"""Etapa 7 — Aplicação Streamlit do Assessor de Investimentos Virtual.

Tela 1: questionário em 4 etapas, com faixas no lugar de valores digitados.
Tela 2: resultado — resumo em 3 frases, carteira explicada classe a classe,
próximos passos, produtos com fatores SHAP e detalhes.

Uso (na raiz do projeto):
    streamlit run app/main.py

Variável de ambiente opcional ASSESSOR_MODELS_DIR aponta para outra pasta de
modelos (útil para demonstração e testes).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # permite "streamlit run app/main.py" a partir da raiz
    sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app import components as ui  # noqa: E402
from src import config  # noqa: E402
from src.advisor import Artefatos, Recomendacao, aconselhar, carregar_artefatos  # noqa: E402
from src.portfolio import (  # noqa: E402
    DIMENSOES, RESPOSTAS_LEGIVEIS, explicar_classe, por_mil, proximos_passos, resumo_simples, risco_carteira,
)

MODELS_DIR = Path(os.environ.get("ASSESSOR_MODELS_DIR", config.MODELS_DIR))

st.set_page_config(page_title="Assessor de Investimentos Virtual", page_icon="📊", layout="centered")


@st.cache_resource(show_spinner="Carregando modelos...")
def obter_artefatos(models_dir: str) -> Artefatos:
    """Carrega os modelos uma única vez por sessão do servidor."""
    pasta = Path(models_dir)
    return carregar_artefatos(
        pasta / config.SEGMENTATION_MODEL_FILE.name,
        pasta / config.REC_MODEL_FILE.name,
        pasta / config.PREP_STATS_FILE.name,
    )


def md(texto: str) -> str:
    """Escapa "$" para o Markdown do Streamlit: "R$ 640 de cada R$ 1.000" viraria fórmula LaTeX."""
    return texto.replace("$", "\\$")


def aviso_legal() -> None:
    st.warning(config.DISCLAIMER, icon="⚠️")


# ---------------------------------------------------------------------------
# Estado do assistente
# ---------------------------------------------------------------------------
# respostas: dict persistente com TODAS as respostas. Os widgets de uma etapa somem
# quando o usuário avança (e o Streamlit apaga o estado deles), por isso cada clique
# em Avançar/Voltar copia os valores da etapa para "respostas" antes de mudar de tela.
def iniciar_estado() -> None:
    st.session_state.setdefault("etapa", 0)
    st.session_state.setdefault("respostas", ui.respostas_padrao())


def salvar_etapa() -> None:
    campos = ui.ETAPAS[st.session_state.etapa][2]
    for campo in campos:
        chave = f"w_{campo}"
        if chave in st.session_state:
            st.session_state.respostas[campo] = st.session_state[chave]


def avancar() -> None:
    salvar_etapa()
    st.session_state.etapa += 1


def voltar() -> None:
    salvar_etapa()
    st.session_state.etapa -= 1


def finalizar() -> None:
    """Callback do último botão: valida, calcula e troca para a tela de resultado."""
    salvar_etapa()
    q, erros = ui.montar_questionario(st.session_state.respostas)
    st.session_state.erros = erros
    if erros:
        return
    st.session_state.resultado = aconselhar(q, obter_artefatos(str(MODELS_DIR)))
    st.session_state.avisos = ui.avisos_de_consistencia(q)


def ajustar_respostas() -> None:
    """Volta ao questionário mantendo as respostas, para o usuário mudar só o que quiser."""
    for chave in ("resultado", "avisos", "erros"):
        st.session_state.pop(chave, None)
    st.session_state.etapa = 0


def recomecar() -> None:
    ajustar_respostas()
    st.session_state.respostas = ui.respostas_padrao()


# ---------------------------------------------------------------------------
# Tela 1 — Questionário em etapas
# ---------------------------------------------------------------------------
def desenhar_pergunta(campo: str) -> None:
    p = ui.PERGUNTAS[campo]
    atual = st.session_state.respostas[campo]
    chave = f"w_{campo}"
    if p.tipo == "faixa":
        st.select_slider(p.texto, options=p.opcoes, value=atual, format_func=p.rotulo, key=chave, help=p.ajuda)
    elif p.tipo == "opcao":
        st.radio(p.texto, p.opcoes, index=p.opcoes.index(atual), format_func=p.rotulo, key=chave,
                 horizontal=p.horizontal, help=p.ajuda)
    elif p.tipo == "numero":
        st.number_input(p.texto, min_value=18, max_value=100, value=int(atual), step=1, key=chave, help=p.ajuda)
    elif p.tipo == "multipla":
        st.multiselect(p.texto, p.opcoes, default=atual, format_func=p.rotulo, key=chave, help=p.ajuda,
                       placeholder="Escolha um ou mais")


def tela_questionario() -> None:
    etapa = st.session_state.etapa
    titulo, descricao, campos = ui.ETAPAS[etapa]
    total = len(ui.ETAPAS)
    st.progress((etapa + 1) / total, text=f"Etapa {etapa + 1} de {total} · {titulo}")
    with st.container(border=True):
        st.subheader(titulo)
        st.caption(descricao)
        for campo in campos:
            desenhar_pergunta(campo)

    for erro in st.session_state.get("erros", []):
        st.error(erro)

    c_voltar, _, c_avancar = st.columns([1, 1, 1.4])
    if etapa > 0:
        c_voltar.button("← Voltar", on_click=voltar, key="btn_voltar", use_container_width=True)
    if etapa < total - 1:
        c_avancar.button("Avançar →", on_click=avancar, key="btn_avancar", type="primary", use_container_width=True)
    else:
        c_avancar.button("Ver minha recomendação", on_click=finalizar, key="btn_ver", type="primary",
                         use_container_width=True)


# ---------------------------------------------------------------------------
# Tela 2 — Resultado
# ---------------------------------------------------------------------------
def secao_resumo(res: Recomendacao) -> None:
    c = res.carteira
    with st.container(border=True):
        st.markdown("#### Em resumo")
        for frase in resumo_simples(c):
            st.markdown(md(f"- {frase}"))

    _, rotulo_risco = risco_carteira(c)
    m1, m2, m3 = st.columns(3)
    m1.metric("Perfil de risco", c.perfil_efetivo.capitalize())
    m2.metric("Pontuação", f"{c.perfil.pontos} / {c.perfil.pontos_max}")
    m3.metric("Risco da carteira", rotulo_risco)
    # Fora do st.metric: nomes de segmento longos seriam truncados (o metric não quebra linha)
    st.markdown(f"**Seu segmento de clientes:** {res.cluster_nome}")

    if c.saude.modo_protecao:
        st.error(
            "**Modo proteção ativado.** Antes de investir com risco, organize a base financeira. "
            "Ações, multimercado e previdência ficam de fora por enquanto.",
            icon="🛡️",
        )
        for alerta in c.saude.alertas:
            st.warning(md(alerta))
    else:
        for alerta in c.saude.alertas:
            st.info(md(alerta))
    if c.perfil.limitado_por:
        st.info(
            f"A pontuação indicaria **{c.perfil.perfil_pela_soma}**, mas seguimos a resposta mais prudente: "
            + "; ".join(c.perfil.limitado_por) + "."
        )


def cartao_classe(c, classe: str) -> None:
    info = config.CLASS_INFO[classe]
    pct = c.alocacao[classe]
    with st.container(border=True):
        st.markdown(f"**{pct}% · {info['nome']}**")
        st.progress(pct / 100, text=md(f"R$ {por_mil(pct)} de cada R$ 1.000 investidos"))
        st.write(info["o_que_e"])
        st.markdown(f"**Para que serve:** {info['papel']}")
        st.caption(f"Risco: {config.RISK_LEVEL_LABELS[info['risco']]} · Resgate: {info['resgate']}")
        st.caption(md(f"**Por que {pct}%?** {explicar_classe(c, classe)}"))


def secao_carteira(res: Recomendacao) -> None:
    c = res.carteira
    st.subheader("Sua carteira sugerida")
    st.plotly_chart(ui.grafico_carteira(c.alocacao), use_container_width=True, config={"displayModeBar": False})

    dentro = [k for k, v in sorted(c.alocacao.items(), key=lambda kv: -kv[1]) if v > 0]
    colunas = st.columns(2)
    for i, classe in enumerate(dentro):
        with colunas[i % 2]:
            cartao_classe(c, classe)

    fora = [k for k, v in c.alocacao.items() if v == 0]
    if fora:
        st.caption(
            "**Fora da carteira:** " + ", ".join(config.CLASS_INFO[k]["nome"] for k in fora)
            + ". " + explicar_classe(c, fora[0])
        )

    with st.expander("Como os números foram calculados"):
        st.write(
            f"1. Suas respostas definem o perfil **{c.perfil_efetivo}**, e o perfil define o mínimo e o máximo de cada classe.\n"
            "2. Cada classe começa no mínimo.\n"
            "3. O espaço que sobra vai para as classes mais comuns entre clientes parecidos com você "
            "(afinidade estimada pelo modelo de IA), sem passar do máximo."
        )
        st.dataframe(pd.DataFrame([
            {"Classe": ui.CLASS_SHORT_LABELS[k], "Mínimo": f"{lo:.0f}%", "Máximo": f"{hi:.0f}%",
             "Afinidade do modelo": f"{c.afinidade[k]:.0%}", "Final": f"{c.alocacao[k]}%"}
            for k, (lo, hi) in c.faixas.items()
        ]), hide_index=True, use_container_width=True)


def secao_passos(res: Recomendacao) -> None:
    st.subheader("Próximos passos")
    st.markdown(md("\n".join(f"{i}. {p}" for i, p in enumerate(proximos_passos(res.carteira), 1))))


def secao_produtos(res: Recomendacao) -> None:
    st.subheader("Produtos para conhecer")
    if not res.produtos:
        msg = ("No modo proteção, o foco é reserva e liquidez antes de novos produtos."
               if res.carteira.saude.modo_protecao else
               "Você já tem os produtos mais comuns para o seu perfil. O foco agora é o rebalanceamento.")
        st.info(msg)
        return
    for prod in res.produtos:
        st.markdown(f"**{prod['rotulo']}** · _{prod['classe_br']}_")
        st.progress(min(max(prod["prob"], 0.0), 1.0), text=f"Cerca de {prod['prob']:.0%} dos clientes com perfil parecido têm")
        fatores = ui.fatores_legiveis(prod["fatores"])
        if fatores:
            st.caption("O que mais pesou: " + " · ".join(f"{d} {t}" for t, d in fatores))


def secao_detalhes(res: Recomendacao) -> None:
    with st.expander(f"Seu segmento: {res.cluster_nome}"):
        st.write(res.cluster_descricao)
    with st.expander("Por que este perfil? (pontuação de suitability)"):
        st.dataframe(pd.DataFrame([
            {"Pergunta": DIMENSOES[d], "Sua resposta": RESPOSTAS_LEGIVEIS.get(r, r), "Pontos": pts}
            for d, (r, pts) in res.carteira.perfil.detalhamento.items()
        ]), hide_index=True, use_container_width=True)
        st.caption("0–5 conservador · 6–10 moderado · 11–14 arrojado")
    with st.expander("Explicação completa (texto)"):
        st.markdown(md(res.texto))


def tela_resultado() -> None:
    res: Recomendacao = st.session_state.resultado
    st.header("Sua recomendação")
    for aviso in st.session_state.get("avisos", []):
        st.info(md(aviso), icon="ℹ️")
    secao_resumo(res)
    secao_carteira(res)
    secao_passos(res)
    secao_produtos(res)
    secao_detalhes(res)
    c1, c2 = st.columns(2)
    c1.button("✏️ Ajustar respostas", on_click=ajustar_respostas, key="btn_ajustar", use_container_width=True)
    c2.button("↩ Começar do zero", on_click=recomecar, key="btn_recomecar", use_container_width=True)


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------
def main() -> None:
    st.title("📊 Assessor de Investimentos Virtual")
    aviso_legal()
    try:
        obter_artefatos(str(MODELS_DIR))
    except FileNotFoundError as exc:
        st.error(f"Modelos não encontrados. {exc}")
        st.code("python -m src.prepare_data\npython -m src.segmentation\npython -m src.recommender", language="bash")
        st.stop()

    iniciar_estado()
    if "resultado" in st.session_state:
        tela_resultado()
    else:
        tela_questionario()
    st.caption("Projeto acadêmico de IA Aplicada · dados: Santander Product Recommendation (Kaggle)")


main()
