"""Usuários (D40, D41): validações de cadastro, banco PostgreSQL, login e gerenciamento com soft delete.

Os testes de banco e de API usam o Postgres de testes do conftest (temporário ou o de
ASSESSOR_TEST_DATABASE_URL); sem nenhum, são pulados. As validações rodam sempre."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg import errors

from api import banco
from api import main as api
from api import usuarios
from api.validacao import mascarar_cpf, validar_cpf, validar_email, validar_idade, validar_nome, validar_senha
from src import config

# CPFs válidos (dígitos verificadores corretos), gerados só para teste
CPF_ADMIN = "529.982.247-25"
CPF_ANA = "111.444.777-35"
CPF_BRUNO = "935.411.347-80"

ADMIN = {"nome": "Rafael Shimomura", "cpf": CPF_ADMIN, "email": "admin@exemplo.com", "idade": 30, "senha": "senhaForte1"}
ANA = {"nome": "Ana Maria D'Ávila", "cpf": CPF_ANA, "email": "Ana@Exemplo.com", "idade": "28", "senha": "outraSenha2"}


@pytest.fixture(autouse=True)
def scrypt_rapido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "SCRYPT_N", 2**8)  # mesmo algoritmo, custo menor: testes rápidos


@pytest.fixture
def db(banco_postgres: str) -> str:
    return banco_postgres


@pytest.fixture
def client(db: str) -> TestClient:
    return TestClient(api.app)


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    usuarios.criar_admin(ADMIN)
    r = client.post("/api/auth/login", json={"login": ADMIN["email"], "senha": ADMIN["senha"]})
    return _cabecalho(r.json()["token"])


# ---------------------------------------------------------------------------
# Validações
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cpf", [CPF_ADMIN, "52998224725", " 529.982.247-25 ", "529 982 247 25"])
def test_cpf_valido_com_e_sem_mascara(cpf: str) -> None:
    assert validar_cpf(cpf) == ("52998224725", None)


@pytest.mark.parametrize("cpf", [
    "529.982.247-24",   # dígito verificador errado
    "111.111.111-11",   # repetido passa no cálculo, mas é inválido
    "000.000.000-00",
    "5299822472",       # 10 dígitos
    "529982247251",     # 12 dígitos
    "529.982.247-2a",   # letra
    "５２９.982.247-25",  # algarismos de largura cheia
    "", None, 52998224725,
])
def test_cpf_invalido(cpf: object) -> None:
    valor, erro = validar_cpf(cpf)
    assert valor is None and erro


@pytest.mark.parametrize("nome, esperado", [
    ("Ana Souza", "Ana Souza"),
    ("  joão   da  silva ", "joão da silva"),
    ("Maria D'Ávila", "Maria D'Ávila"),
    ("Ana-Clara Gonçalves", "Ana-Clara Gonçalves"),
    ("Jose\u0301 Souza", "José Souza"),         # acento decomposto (NFD), como o macOS envia
    ("Ana D’Ávila", "Ana D'Ávila"),              # apóstrofo curvo que o celular coloca sozinho
])
def test_nome_valido(nome: str, esperado: str) -> None:
    assert validar_nome(nome) == (esperado, None)


@pytest.mark.parametrize("nome", ["Ana", "Ana 2 Souza", "Ana@Souza Lima", "-Ana Souza", "Ana  - Souza", "Ana Souza'",
                                  "Maria ª Souza", "Ana 😀 Souza",
                                  "A" * (config.NOME_MAX_CARACTERES + 1) + " B", "", "   ", None, 123])
def test_nome_invalido(nome: object) -> None:
    valor, erro = validar_nome(nome)
    assert valor is None and erro


@pytest.mark.parametrize("idade, esperado", [(18, 18), ("18", 18), ("40", 40), (" 40 ", 40), (122, 122), ("122", 122)])
def test_idade_valida(idade: object, esperado: int) -> None:
    assert validar_idade(idade) == (esperado, None)


@pytest.mark.parametrize("idade", ["３０", "٣٠", 17, "17", 1, 0, "0", -1, "-1", "+5", 123, "123", "1000", 30.5, "30.5", "30,5", "1e2", "trinta",
                                   True, "", None])
def test_idade_so_aceita_inteiro_de_maior_ate_o_recorde(idade: object) -> None:
    valor, erro = validar_idade(idade)
    assert valor is None and erro


def test_idade_maxima_e_o_recorde_da_historia() -> None:
    assert config.IDADE_MAXIMA == 122  # Jeanne Calment, 122 anos e 164 dias
    assert config.IDADE_MINIMA == 18   # maioridade, como no questionário


@pytest.mark.parametrize("email, ok", [("Ana@Exemplo.com", True), ("a.b+c@sub.dominio.com.br", True),
                                       ("sem-arroba.com", False), ("a@b", False), ("a b@c.com", False), ("", False)])
def test_email(email: str, ok: bool) -> None:
    valor, erro = validar_email(email)
    assert (erro is None) is ok
    if ok:
        assert valor == email.lower()


@pytest.mark.parametrize("senha, ok", [("senhaForte1", True), ("curta1", False), ("somenteletras", False),
                                       ("1234567890", False), ("", False)])
def test_senha(senha: str, ok: bool) -> None:
    assert (validar_senha(senha)[1] is None) is ok


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------
def test_senha_nunca_fica_em_texto_puro(db: str) -> None:
    with banco.conectar() as con:
        banco.criar_usuario(con, nome="Ana Souza", cpf="11144477735", email="a@b.com", idade=30, senha="senhaForte1")
        guardado = con.execute("SELECT senha_hash FROM usuarios").fetchone()["senha_hash"]
    assert "senhaForte1" not in guardado and guardado.startswith("scrypt$")
    assert banco.conferir_senha("senhaForte1", guardado) and not banco.conferir_senha("errada123", guardado)


def test_banco_recusa_idade_fora_do_limite_mesmo_sem_a_api(db: str) -> None:
    with pytest.raises(errors.CheckViolation), banco.conectar() as con:
        banco.criar_usuario(con, nome="Ana Souza", cpf="11144477735", email="a@b.com", idade=123, senha="senhaForte1")


# ---------------------------------------------------------------------------
# Cadastro e login
# ---------------------------------------------------------------------------
def test_registro_normaliza_e_ja_entra(client: TestClient) -> None:
    r = client.post("/api/auth/registro", json=ANA)
    assert r.status_code == 201
    corpo = r.json()
    u = corpo["usuario"]
    assert u["email"] == "ana@exemplo.com" and u["idade"] == 28 and u["cpf"] == CPF_ANA
    assert u["papel"] == "usuario" and "senha" not in u and "senha_hash" not in u
    assert client.get("/api/auth/eu", headers=_cabecalho(corpo["token"])).json()["id"] == u["id"]


def test_registro_publico_nunca_cria_admin(client: TestClient) -> None:
    r = client.post("/api/auth/registro", json={**ANA, "papel": "admin"})
    assert r.json()["usuario"]["papel"] == "usuario"


def test_registro_devolve_erro_por_campo(client: TestClient) -> None:
    r = client.post("/api/auth/registro", json={"nome": "Ana", "cpf": "123", "email": "x", "idade": "-3", "senha": "abc"})
    assert r.status_code == 422
    assert set(r.json()["detail"]["campos"]) == {"nome", "cpf", "email", "idade", "senha"}


def test_registro_recusa_cpf_e_email_repetidos(client: TestClient) -> None:
    client.post("/api/auth/registro", json=ANA)
    r = client.post("/api/auth/registro", json={**ANA, "email": "outro@exemplo.com", "cpf": "11144477735"})
    assert r.status_code == 409 and "cpf" in r.json()["detail"]["campos"]
    r = client.post("/api/auth/registro", json={**ANA, "cpf": CPF_BRUNO, "email": "ANA@exemplo.com"})
    assert r.status_code == 409 and "email" in r.json()["detail"]["campos"]


def test_login_por_email_ou_cpf(client: TestClient) -> None:
    client.post("/api/auth/registro", json=ANA)
    for login in ("ana@exemplo.com", " ANA@exemplo.com", CPF_ANA, "11144477735"):
        assert client.post("/api/auth/login", json={"login": login, "senha": ANA["senha"]}).status_code == 200
    r = client.post("/api/auth/login", json={"login": "ana@exemplo.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"]["erros"] == ["E-mail/CPF ou senha incorretos."]
    assert client.post("/api/auth/login", json={"login": "ninguem@x.com", "senha": "errada123"}).status_code == 401


def test_logout_invalida_o_token(client: TestClient) -> None:
    token = client.post("/api/auth/registro", json=ANA).json()["token"]
    assert client.post("/api/auth/logout", headers=_cabecalho(token)).status_code == 204
    assert client.get("/api/auth/eu", headers=_cabecalho(token)).status_code == 401


def test_sem_token_ou_token_falso(client: TestClient) -> None:
    assert client.get("/api/auth/eu").status_code == 401
    assert client.get("/api/auth/eu", headers=_cabecalho("inventado")).status_code == 401


def test_regras_vem_do_config(client: TestClient) -> None:
    r = client.get("/api/auth/regras").json()
    assert r["idade_minima"] == config.IDADE_MINIMA and r["idade_maxima"] == config.IDADE_MAXIMA


# ---------------------------------------------------------------------------
# Gerenciamento (admin)
# ---------------------------------------------------------------------------
def test_usuario_comum_nao_gerencia(client: TestClient) -> None:
    token = client.post("/api/auth/registro", json=ANA).json()["token"]
    for metodo, rota in (("get", "/api/usuarios"), ("post", "/api/usuarios"), ("delete", "/api/usuarios/1")):
        assert getattr(client, metodo)(rota, headers=_cabecalho(token)).status_code == 403
    assert client.get("/api/usuarios").status_code == 401


def test_admin_cria_lista_e_edita(client: TestClient, admin: dict[str, str]) -> None:
    r = client.post("/api/usuarios", headers=admin, json={**ANA, "papel": "admin"})
    assert r.status_code == 201 and r.json()["papel"] == "admin"
    ana_id = r.json()["id"]

    lista = client.get("/api/usuarios", headers=admin).json()
    assert [u["nome"] for u in lista] == ["Ana Maria D'Ávila", "Rafael Shimomura"]
    assert lista[0]["cpf"] == mascarar_cpf("11144477735")  # listagem não expõe o CPF inteiro
    assert [u["id"] for u in client.get("/api/usuarios?busca=4447", headers=admin).json()] == [ana_id]
    assert [u["nome"] for u in client.get("/api/usuarios?busca=SHIMO", headers=admin).json()] == ["Rafael Shimomura"]

    edicao = {"nome": "Ana Maria Souza", "email": "ana.souza@exemplo.com", "idade": 29, "papel": "usuario", "senha": ""}
    r = client.put(f"/api/usuarios/{ana_id}", headers=admin, json=edicao)
    assert r.status_code == 200 and r.json()["nome"] == "Ana Maria Souza" and r.json()["papel"] == "usuario"
    # senha vazia mantém a antiga
    assert client.post("/api/auth/login", json={"login": "ana.souza@exemplo.com", "senha": ANA["senha"]}).status_code == 200

    r = client.put(f"/api/usuarios/{ana_id}", headers=admin, json={**edicao, "idade": 130})
    assert r.status_code == 422 and "idade" in r.json()["detail"]["campos"]
    r = client.put(f"/api/usuarios/{ana_id}", headers=admin, json={**edicao, "email": ADMIN["email"]})
    assert r.status_code == 409


def test_troca_de_senha_derruba_sessoes(client: TestClient, admin: dict[str, str]) -> None:
    corpo = client.post("/api/auth/registro", json=ANA).json()
    ana = _cabecalho(corpo["token"])
    edicao = {"nome": ANA["nome"], "email": "ana@exemplo.com", "idade": 28, "papel": "usuario", "senha": "novaSenha9"}
    assert client.put(f"/api/usuarios/{corpo['usuario']['id']}", headers=admin, json=edicao).status_code == 200
    assert client.get("/api/auth/eu", headers=ana).status_code == 401
    assert client.post("/api/auth/login", json={"login": "ana@exemplo.com", "senha": "novaSenha9"}).status_code == 200


def test_soft_delete_e_restauracao(client: TestClient, admin: dict[str, str], db: str) -> None:
    corpo = client.post("/api/auth/registro", json=ANA).json()
    ana_id, ana = corpo["usuario"]["id"], _cabecalho(corpo["token"])

    assert client.delete(f"/api/usuarios/{ana_id}", headers=admin).status_code == 204
    # a linha continua no banco, só marcada
    with banco.conectar() as con:
        assert con.execute("SELECT excluido_em FROM usuarios WHERE id = %s", (ana_id,)).fetchone()["excluido_em"]
    assert client.get("/api/auth/eu", headers=ana).status_code == 401  # sessão encerrada
    assert client.post("/api/auth/login", json={"login": "ana@exemplo.com", "senha": ANA["senha"]}).status_code == 401
    assert ana_id not in [u["id"] for u in client.get("/api/usuarios", headers=admin).json()]
    excluidos = client.get("/api/usuarios?excluidos=true", headers=admin).json()
    assert next(u for u in excluidos if u["id"] == ana_id)["excluido_em"]
    assert client.delete(f"/api/usuarios/{ana_id}", headers=admin).status_code == 409  # já excluída
    edicao = {"nome": "Ana Souza", "email": "ana@exemplo.com", "idade": 28, "papel": "usuario"}
    r = client.put(f"/api/usuarios/{ana_id}", headers=admin, json=edicao)
    assert r.status_code == 409 and "Restaure" in r.json()["detail"]["erros"][0]

    # CPF/e-mail de conta desativada não são recadastrados: a conta é restaurada
    r = client.post("/api/auth/registro", json=ANA)
    assert r.status_code == 409 and "desativada" in r.json()["detail"]["erros"][0]

    r = client.post(f"/api/usuarios/{ana_id}/restaurar", headers=admin)
    assert r.status_code == 200 and r.json()["excluido_em"] is None
    assert client.post("/api/auth/login", json={"login": "ana@exemplo.com", "senha": ANA["senha"]}).status_code == 200
    assert client.post(f"/api/usuarios/{ana_id}/restaurar", headers=admin).status_code == 409


def test_admin_nao_se_exclui_nem_se_rebaixa(client: TestClient, admin: dict[str, str]) -> None:
    eu = client.get("/api/auth/eu", headers=admin).json()
    assert client.delete(f"/api/usuarios/{eu['id']}", headers=admin).status_code == 409
    edicao = {"nome": eu["nome"], "email": eu["email"], "idade": eu["idade"], "papel": "usuario"}
    assert client.put(f"/api/usuarios/{eu['id']}", headers=admin, json=edicao).status_code == 409
    assert client.get("/api/auth/eu", headers=admin).json()["papel"] == "admin"


def test_usuario_inexistente(client: TestClient, admin: dict[str, str]) -> None:
    assert client.get("/api/usuarios/999", headers=admin).status_code == 404
    assert client.delete("/api/usuarios/999", headers=admin).status_code == 404


def test_cli_criar_admin(db: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    respostas = iter([ADMIN["nome"], ADMIN["cpf"], ADMIN["email"], str(ADMIN["idade"])])
    monkeypatch.setattr("builtins.input", lambda _: next(respostas))
    monkeypatch.setattr(usuarios.getpass, "getpass", lambda _: ADMIN["senha"])
    assert usuarios.main(["criar-admin"]) == 0
    with banco.conectar() as con:
        assert banco.listar_usuarios(con)[0]["papel"] == "admin"
    with pytest.raises(ValueError, match="Já existe"):
        usuarios.criar_admin(ADMIN)


# ---------------------------------------------------------------------------
# Bloqueio de login, dados próprios, troca de senha e exclusão definitiva
# ---------------------------------------------------------------------------
def _login(client: TestClient, login: str, senha: str) -> int:
    return client.post("/api/auth/login", json={"login": login, "senha": senha}).status_code


def test_bloqueia_login_depois_de_varias_senhas_erradas(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    client.post("/api/auth/registro", json=ANA)
    client.post("/api/auth/registro", json={**ADMIN, "idade": 40})
    for _ in range(config.LOGIN_MAX_TENTATIVAS - 2):
        assert _login(client, "ana@exemplo.com", "errada123") == 401
    assert _login(client, CPF_ANA, "errada123") == 401  # errar pelo CPF soma no contador da mesma conta
    assert _login(client, "ana@exemplo.com", "errada123") == 429  # a 5ª falha já bloqueia
    r = client.post("/api/auth/login", json={"login": "111.444.777-35", "senha": ANA["senha"]})
    assert r.status_code == 429 and "Tente de novo em" in r.json()["detail"]["erros"][0]  # nem a senha certa entra
    assert _login(client, ADMIN["email"], ADMIN["senha"]) == 200  # as outras contas seguem livres

    # passado o intervalo, volta a aceitar
    with banco.conectar() as con:
        con.execute("UPDATE tentativas_login SET momento = '2000-01-01T00:00:00+00:00'")
    assert _login(client, "ana@exemplo.com", ANA["senha"]) == 200


def test_login_certo_zera_as_falhas(client: TestClient) -> None:
    client.post("/api/auth/registro", json=ANA)
    for _ in range(config.LOGIN_MAX_TENTATIVAS - 1):
        _login(client, "ana@exemplo.com", "errada123")
    assert _login(client, "ana@exemplo.com", ANA["senha"]) == 200
    assert _login(client, "ana@exemplo.com", "errada123") == 401  # contagem recomeçou


def test_usuario_edita_os_proprios_dados(client: TestClient) -> None:
    corpo = client.post("/api/auth/registro", json=ANA).json()
    ana = _cabecalho(corpo["token"])
    r = client.put("/api/auth/eu", headers=ana, json={"nome": "Ana Maria Souza", "email": "nova@exemplo.com", "idade": "29",
                                                      "papel": "admin", "cpf": CPF_BRUNO})
    assert r.status_code == 200
    u = r.json()
    assert (u["nome"], u["email"], u["idade"]) == ("Ana Maria Souza", "nova@exemplo.com", 29)
    assert u["papel"] == "usuario" and u["cpf"] == CPF_ANA  # tipo e CPF não mudam por aqui
    r = client.put("/api/auth/eu", headers=ana, json={"nome": "Ana", "email": "x", "idade": 17})
    assert r.status_code == 422 and set(r.json()["detail"]["campos"]) == {"nome", "email", "idade"}
    assert client.put("/api/auth/eu", json={"nome": "Ana Souza"}).status_code == 401


def test_usuario_troca_a_propria_senha(client: TestClient) -> None:
    corpo = client.post("/api/auth/registro", json=ANA).json()
    antigo = _cabecalho(corpo["token"])
    outro_aparelho = _cabecalho(client.post("/api/auth/login", json={"login": CPF_ANA, "senha": ANA["senha"]}).json()["token"])

    r = client.post("/api/auth/senha", headers=antigo, json={"senha_atual": "errada123", "nova_senha": "novaSenha9"})
    assert r.status_code == 422 and "senha_atual" in r.json()["detail"]["campos"]
    r = client.post("/api/auth/senha", headers=antigo, json={"senha_atual": ANA["senha"], "nova_senha": "curta"})
    assert r.status_code == 422 and "nova_senha" in r.json()["detail"]["campos"]
    r = client.post("/api/auth/senha", headers=antigo, json={"senha_atual": ANA["senha"], "nova_senha": ANA["senha"]})
    assert r.status_code == 422

    r = client.post("/api/auth/senha", headers=antigo, json={"senha_atual": ANA["senha"], "nova_senha": "novaSenha9"})
    assert r.status_code == 200
    novo = _cabecalho(r.json()["token"])
    assert client.get("/api/auth/eu", headers=novo).status_code == 200
    assert client.get("/api/auth/eu", headers=antigo).status_code == 401
    assert client.get("/api/auth/eu", headers=outro_aparelho).status_code == 401
    assert _login(client, "ana@exemplo.com", "novaSenha9") == 200


def test_exclusao_definitiva_so_depois_do_soft_delete(client: TestClient, admin: dict[str, str]) -> None:
    corpo = client.post("/api/auth/registro", json=ANA).json()
    ana_id = corpo["usuario"]["id"]
    with banco.conectar() as con:
        banco.salvar_recomendacao(con, ana_id, "moderado", {"idade": 28}, {"perfil": {}})
        banco.registrar_falha_login(con, "ana@exemplo.com")
        banco.registrar_falha_login(con, "ninguem@exemplo.com")

    r = client.delete(f"/api/usuarios/{ana_id}/definitivo", headers=admin)
    assert r.status_code == 409  # ainda ativa: precisa do soft delete antes
    client.delete(f"/api/usuarios/{ana_id}", headers=admin)
    assert client.delete(f"/api/usuarios/{ana_id}/definitivo", headers=admin).status_code == 204

    with banco.conectar() as con:
        for tabela in ("usuarios", "sessoes", "recomendacoes"):
            assert con.execute(f"SELECT count(*) AS n FROM {tabela} WHERE {'id' if tabela == 'usuarios' else 'usuario_id'} = %s",
                               (ana_id,)).fetchone()["n"] == 0
        assert [r["login"] for r in con.execute("SELECT login FROM tentativas_login")] == ["email:ninguem@exemplo.com"]
    assert client.get(f"/api/usuarios/{ana_id}", headers=admin).status_code == 404
    # sem rastro: o mesmo CPF pode criar uma conta nova
    assert client.post("/api/auth/registro", json=ANA).status_code == 201


def test_usuario_comum_nao_apaga_definitivo(client: TestClient) -> None:
    token = client.post("/api/auth/registro", json=ANA).json()["token"]
    assert client.delete("/api/usuarios/1/definitivo", headers=_cabecalho(token)).status_code == 403


def test_banco_fora_do_ar_vira_503(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSESSOR_DATABASE_URL", "postgresql://ninguem@127.0.0.1:1/nada")
    r = TestClient(api.app).post("/api/auth/login", json={"login": "a@b.com", "senha": "senhaForte1"})
    assert r.status_code == 503 and "PostgreSQL" in r.json()["detail"]["erros"][0]


def test_formato_invalido_vira_erro_em_portugues(client: TestClient, admin: dict[str, str]) -> None:
    r = client.post("/api/auth/login", json=["não é objeto"])
    assert r.status_code == 422 and r.json()["detail"]["erros"][0].startswith("A requisição veio num formato inválido")
    r = client.get("/api/usuarios?excluidos=talvez", headers=admin)
    assert r.status_code == 422 and "excluidos" in r.json()["detail"]["erros"][0]
