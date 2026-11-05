---
name: ambiente-virtual
description: Garante que o projeto Assessor de Investimentos Virtual seja usado dentro de um ambiente virtual Python 3.12 (.venv). Use antes de instalar dependências, rodar o pipeline, os testes, o app Streamlit ou a API, e sempre que aparecer ModuleNotFoundError, versão de Python diferente de 3.12/3.11 (ex.: 3.13) ou um caminho de Python global (ex.: AppData\Local\Programs\Python\...) num traceback.
---

# Ambiente virtual obrigatório

Todo comando Python deste projeto roda **dentro do ambiente virtual `.venv`, criado com Python 3.12**,
na raiz do repositório. Nunca instale as dependências no Python global da máquina.

## Por quê

- As versões em `requirements.txt` são fixadas para reprodutibilidade. `numba` e `contourpy` estão presos
  para evitar o numpy 2.x, que quebra o `shap` 0.46 (D21 em `docs/decisoes.md`). Misturar com pacotes
  instalados globalmente leva a erros difíceis de rastrear.
- O Python global pode ter outra versão (ex.: 3.13) e outras bibliotecas. Já aconteceu de o
  `python -m src.raio_x` rodar com o Python global, fora da `.venv`, sem o `openpyxl` do projeto.
- Cada integrante do grupo precisa ter **o mesmo ambiente** para que os resultados (modelos, relatórios e
  figuras) batam.

## Criar (uma vez)

Windows (PowerShell), na raiz do projeto:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Se o PowerShell bloquear o `Activate.ps1`, libere scripts só para o usuário atual:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Ativar (a cada novo terminal)

```powershell
.venv\Scripts\Activate.ps1
```

O prompt passa a começar com `(.venv)`. Sem isso, os comandos usam o Python global.

## Conferir antes de rodar qualquer coisa

```powershell
python -c "import sys; print(sys.version); print(sys.prefix)"
```

Esperado: versão **3.12.x** (3.11.x também serve) e `sys.prefix` terminando em `.venv`, dentro da pasta do projeto. Se
aparecer outra versão ou um caminho como `AppData\Local\Programs\Python\...`, o ambiente **não** está
ativo: ative-o e rode de novo.

## Uso no dia a dia (sempre com a `.venv` ativa)

```powershell
python -m src.pipeline           # pipeline completo
python -m src.raio_x             # só a referência brasileira (Raio X ANBIMA)
pytest                           # testes
streamlit run app/main.py        # app Streamlit
uvicorn api.main:app --port 8000 # API do front React
```

- Rode tudo a partir da **raiz** do projeto e como módulo (`python -m src.X`), nunca `python src/X.py`.
- Dependência nova: instale com a `.venv` ativa e **adicione ao `requirements.txt` com versão fixada**
  (`pacote==x.y.z`), para o grupo inteiro receber a mesma versão.
- A `.venv` não vai para o git (está no `.gitignore`). Cada pessoa cria a sua.

## Problemas comuns

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `ModuleNotFoundError` (ex.: `openpyxl`, `lightgbm`) | `.venv` não ativada, ou `requirements.txt` mudou | Ativar a `.venv` e rodar `pip install -r requirements.txt` |
| Traceback com caminho do Python global (`AppData\Local\Programs\Python\...`) | Usando o Python global | Ativar a `.venv` (criada com `py -3.12`) |
| Erro ao instalar numpy/numba ("compilando", "Microsoft Visual C++") | `.venv` criada com Python 3.13 | Recriar a `.venv` com `py -3.12` |
| `py -3.12` não encontrado | Python 3.12 não instalado | Instalar o Python 3.12 (python.org) e recriar a `.venv` |
| Erro do `shap`/`numba` com numpy 2.x | Dependências fora das versões fixadas | Apagar a `.venv`, recriar e reinstalar pelo `requirements.txt` |
| Falha ao criar a `.venv` no Windows | Caminho muito longo (limite de 260 caracteres) | Clonar o projeto num caminho curto, ex.: `C:\projetos\assessor` |

Para recriar do zero:

```powershell
deactivate
Remove-Item -Recurse -Force .venv
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
