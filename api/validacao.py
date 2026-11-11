"""Validação dos campos de cadastro de usuário (D40).

Funções puras, sem banco nem FastAPI: cada uma recebe o valor bruto vindo do
formulário e devolve ``(valor_normalizado, None)`` ou ``(None, mensagem_de_erro)``.
O front só filtra o que pode ser digitado; a regra vale aqui, no servidor.
"""

from __future__ import annotations

import re
from typing import Any

from src import config

Resultado = tuple[Any, str | None]

_SEPARADORES_NOME = " '-"
_EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
                    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$")


def _texto(valor: Any) -> str | None:
    return valor if isinstance(valor, str) else None


def validar_cpf(valor: Any) -> Resultado:
    """Aceita com ou sem máscara (000.000.000-00) e devolve só os 11 dígitos."""
    texto = _texto(valor)
    if texto is None or not texto.strip():
        return None, "Informe o CPF."
    if re.fullmatch(r"[\d.\-\s]+", texto) is None:
        return None, "O CPF só pode ter números (pontos e traço são opcionais)."
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) != 11:
        return None, "O CPF precisa ter 11 dígitos."
    if digitos == digitos[0] * 11:  # 000.000.000-00, 111.111.111-11... passam no cálculo, mas são inválidos
        return None, "CPF inválido."
    for tamanho in (9, 10):
        soma = sum(int(d) * peso for d, peso in zip(digitos[:tamanho], range(tamanho + 1, 1, -1)))
        verificador = (soma * 10) % 11 % 10
        if verificador != int(digitos[tamanho]):
            return None, "CPF inválido: os dígitos verificadores não conferem."
    return digitos, None


def formatar_cpf(digitos: str) -> str:
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


def mascarar_cpf(digitos: str) -> str:
    """Mostra só o miolo do CPF (como nos comprovantes de Pix): ***.456.789-**."""
    return f"***.{digitos[3:6]}.{digitos[6:9]}-**"


def validar_nome(valor: Any) -> Resultado:
    """Nome e sobrenome: só letras (com acento), espaço, apóstrofo e hífen."""
    texto = _texto(valor)
    if texto is None or not texto.strip():
        return None, "Informe o nome completo."
    nome = " ".join(texto.split())
    if not config.NOME_MIN_CARACTERES <= len(nome) <= config.NOME_MAX_CARACTERES:
        return None, (f"O nome precisa ter entre {config.NOME_MIN_CARACTERES} e "
                      f"{config.NOME_MAX_CARACTERES} caracteres.")
    if any(not (c.isalpha() or c in _SEPARADORES_NOME) for c in nome):
        return None, "O nome só pode ter letras, espaços, apóstrofo (') e hífen (-)."
    if not (nome[0].isalpha() and nome[-1].isalpha()) or re.search(r"[ '\-]{2,}", nome):
        return None, "O nome não pode começar, terminar ou ter dois sinais seguidos (espaço, ' ou -)."
    if len(nome.split(" ")) < 2:
        return None, "Informe nome e sobrenome."
    return nome, None


def validar_idade(valor: Any) -> Resultado:
    """Inteiro positivo até o maior registro de idade da história. Recusa sinal, decimal e notação científica."""
    if isinstance(valor, bool):  # bool é subclasse de int em Python
        return None, "A idade precisa ser um número inteiro."
    if isinstance(valor, int):
        idade = valor
    elif isinstance(valor, str) and re.fullmatch(r"\d{1,3}", valor.strip()):
        idade = int(valor.strip())
    elif valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, "Informe a idade."
    else:
        return None, "A idade só pode ter números inteiros, sem sinal, ponto ou vírgula."
    if not config.IDADE_MINIMA <= idade <= config.IDADE_MAXIMA:
        return None, (f"A idade precisa estar entre {config.IDADE_MINIMA} e {config.IDADE_MAXIMA} anos "
                      f"({config.IDADE_MAXIMA} é o maior registro de idade da história).")
    return idade, None


def validar_email(valor: Any) -> Resultado:
    texto = _texto(valor)
    if texto is None or not texto.strip():
        return None, "Informe o e-mail."
    email = texto.strip().lower()
    if len(email) > config.EMAIL_MAX_CARACTERES or _EMAIL.fullmatch(email) is None:
        return None, "E-mail inválido."
    return email, None


def validar_senha(valor: Any) -> Resultado:
    texto = _texto(valor)
    if not texto:
        return None, "Informe a senha."
    if not config.SENHA_MIN_CARACTERES <= len(texto) <= config.SENHA_MAX_CARACTERES:
        return None, (f"A senha precisa ter entre {config.SENHA_MIN_CARACTERES} e "
                      f"{config.SENHA_MAX_CARACTERES} caracteres.")
    if not (any(c.isalpha() for c in texto) and any(c.isdigit() for c in texto)):
        return None, "A senha precisa ter pelo menos uma letra e um número."
    return texto, None


def validar_papel(valor: Any) -> Resultado:
    if valor not in config.PAPEIS_USUARIO:
        return None, "Tipo de usuário inválido."
    return valor, None


VALIDADORES = {
    "nome": validar_nome,
    "cpf": validar_cpf,
    "email": validar_email,
    "idade": validar_idade,
    "senha": validar_senha,
    "papel": validar_papel,
}


def validar(dados: dict[str, Any], campos: list[str]) -> tuple[dict[str, Any], dict[str, str]]:
    """Valida os campos pedidos; devolve (valores normalizados, erros por campo)."""
    valores: dict[str, Any] = {}
    erros: dict[str, str] = {}
    for campo in campos:
        valor, erro = VALIDADORES[campo](dados.get(campo))
        if erro:
            erros[campo] = erro
        else:
            valores[campo] = valor
    return valores, erros
