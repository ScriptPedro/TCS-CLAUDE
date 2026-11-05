"""Acesso ao modelo de linguagem do assessor conversacional (D38).

Este módulo só conversa com o fornecedor (hoje o Google Gemini). Ele não conhece
carteira, perfil nem regras: recebe instruções, mensagens e ferramentas e devolve
texto ou pedidos de ferramenta. Trocar de fornecedor = escrever outra classe com o
mesmo método ``gerar``.

A chave vem da variável de ambiente ``GEMINI_API_KEY`` (nunca do código ou do git).
Sem chave, ``obter_provedor()`` devolve ``None`` e o app segue sem o chat.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from src import config
from src.utils import get_logger

logger = get_logger(__name__)


class AssistenteIndisponivel(RuntimeError):
    """O modelo não respondeu (sem chave, sem rede, limite do plano, erro do serviço)."""


@dataclass(frozen=True)
class Ferramenta:
    """Função que o modelo pode pedir para executar. ``parametros`` é um JSON Schema."""

    nome: str
    descricao: str
    parametros: dict[str, Any]


@dataclass(frozen=True)
class ChamadaFerramenta:
    nome: str
    argumentos: dict[str, Any]
    id: str | None = None


@dataclass
class Mensagem:
    """Uma mensagem da conversa.

    papel: "usuario" | "modelo" | "ferramenta". ``bruto`` guarda a mensagem original
    do fornecedor (o Gemini exige receber de volta exatamente o que mandou, incluindo
    assinaturas internas, quando pede uma ferramenta).
    """

    papel: str
    texto: str = ""
    chamadas: list[ChamadaFerramenta] = field(default_factory=list)
    nome_ferramenta: str | None = None
    resultado: dict[str, Any] | None = None
    id_chamada: str | None = None
    bruto: Any = None


@dataclass
class RespostaLLM:
    texto: str
    chamadas: list[ChamadaFerramenta]
    bruto: Any = None


class Provedor(Protocol):
    def gerar(self, sistema: str, mensagens: list[Mensagem], ferramentas: list[Ferramenta]) -> RespostaLLM: ...


# ---------------------------------------------------------------------------
# Google Gemini
# ---------------------------------------------------------------------------
class ProvedorGemini:
    """Gemini via SDK ``google-genai``, com chamada de ferramentas manual (sem execução automática)."""

    def __init__(self, api_key: str, modelo: str) -> None:
        from google import genai  # import tardio: o resto do projeto não depende do SDK
        from google.genai import types

        self._types = types
        self.modelo = modelo
        self._cliente = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=config.LLM_TIMEOUT_SECONDS * 1000)
        )

    def _conteudos(self, mensagens: list[Mensagem]) -> list[Any]:
        t = self._types
        conteudos: list[Any] = []
        for m in mensagens:
            if m.papel == "ferramenta":
                parte = t.Part(function_response=t.FunctionResponse(
                    id=m.id_chamada, name=m.nome_ferramenta, response={"resultado": m.resultado}))
                # respostas de chamadas paralelas vão juntas na mesma mensagem
                if conteudos and conteudos[-1].role == "tool":
                    conteudos[-1].parts.append(parte)
                else:
                    conteudos.append(t.Content(role="tool", parts=[parte]))
            elif m.papel == "modelo" and m.bruto is not None:
                conteudos.append(m.bruto)
            else:
                papel = "model" if m.papel == "modelo" else "user"
                conteudos.append(t.Content(role=papel, parts=[t.Part.from_text(text=m.texto)]))
        return conteudos

    def gerar(self, sistema: str, mensagens: list[Mensagem], ferramentas: list[Ferramenta]) -> RespostaLLM:
        t = self._types
        from google.genai import errors

        cfg = t.GenerateContentConfig(
            system_instruction=sistema,
            temperature=config.LLM_TEMPERATURE,
            max_output_tokens=config.LLM_MAX_OUTPUT_TOKENS,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
            tools=[t.Tool(function_declarations=[
                t.FunctionDeclaration(name=f.nome, description=f.descricao, parameters_json_schema=f.parametros)
                for f in ferramentas
            ])] if ferramentas else None,
        )
        try:
            resp = self._cliente.models.generate_content(model=self.modelo, contents=self._conteudos(mensagens), config=cfg)
        except errors.APIError as exc:
            logger.warning("Gemini respondeu erro %s: %s", exc.code, exc.message)
            if exc.code == 429:
                raise AssistenteIndisponivel(
                    "O limite de uso do plano gratuito do Gemini foi atingido. Tente de novo em alguns minutos.") from exc
            if exc.code in (401, 403):
                raise AssistenteIndisponivel("A chave do Gemini foi recusada. Confira a variável GEMINI_API_KEY.") from exc
            raise AssistenteIndisponivel("O serviço do Gemini não respondeu agora. Tente de novo em instantes.") from exc
        except Exception as exc:  # rede, timeout, resposta inesperada
            logger.warning("Falha ao chamar o Gemini: %r", exc)
            raise AssistenteIndisponivel("Não foi possível falar com o Gemini (sem internet ou tempo esgotado).") from exc

        candidato = (resp.candidates or [None])[0]
        conteudo = getattr(candidato, "content", None)
        partes = list(getattr(conteudo, "parts", None) or [])
        texto = "".join(p.text for p in partes if getattr(p, "text", None) and not getattr(p, "thought", False))
        chamadas = [ChamadaFerramenta(fc.name, dict(fc.args or {}), fc.id) for fc in (resp.function_calls or [])]
        return RespostaLLM(texto.strip(), chamadas, conteudo)


def obter_provedor() -> Provedor | None:
    """Gemini configurado pela variável de ambiente, ou ``None`` se não houver chave."""
    chave = os.environ.get(config.LLM_API_KEY_ENV, "").strip()
    if not chave:
        return None
    return ProvedorGemini(chave, os.environ.get(config.LLM_MODEL_ENV, "").strip() or config.LLM_DEFAULT_MODEL)
