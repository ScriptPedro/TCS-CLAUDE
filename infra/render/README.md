# Deploy no Render (API + PostgreSQL) com o front no GitHub Pages

A API FastAPI e o PostgreSQL dos usuários sobem no **Render**, os dois no plano grátis. O front React
é publicado no **GitHub Pages** por um workflow do GitHub Actions. A escolha está na decisão D42
(`docs/decisoes.md`).

```
GitHub Pages  https://scriptpedro.github.io/TCS-CLAUDE/      (.github/workflows/pages.yml)
     │  fetch + "Authorization: Bearer <token>"  (CORS liberado só para essa origem)
     ▼
Render web service "assessor-api"   https://<nome>.onrender.com   (render.yaml, mesmo Dockerfile)
     ├─ ao ligar: baixa ASSESSOR_MODELS_URL (.zip) → /models     (api/modelos_remotos.py)
     └─ ASSESSOR_DATABASE_URL (endereço interno) ──► Render Postgres "assessor-db"
```

Tudo é descrito em arquivos versionados: [`render.yaml`](../../render.yaml) (Blueprint do Render) e
[`.github/workflows/pages.yml`](../../.github/workflows/pages.yml). Não há Terraform aqui.

## O que o plano grátis impõe

| Limite | Efeito no app |
|---|---|
| A API **dorme após 15 min** sem acesso | O primeiro acesso depois disso leva **~1 minuto**. Abra o site um pouco antes de apresentar. |
| **512 MB de RAM** | Com modelos pequenos a API usa ~340 MB. Confira em *Metrics* com os modelos reais. |
| Sem disco persistente | Os modelos são baixados a cada vez que a API liga (poucos segundos). |
| O **Postgres grátis expira 30 dias** depois de criado | Os usuários somem com ele. Recrie o banco (ou mude o plano) antes de uma apresentação. Confira o prazo atual no painel. |
| 750 horas de instância por mês | Dá para um serviço ligado o mês inteiro. |

## 1. Publicar os modelos (uma vez, e de novo a cada retreino)

O Render não tem a pasta `models/`, que não vai para o git. A API baixa um `.zip` com os modelos
de uma URL. O jeito mais simples é anexar o `.zip` a uma *release* do GitHub.

1. Gere os modelos (`python -m src.pipeline`) e compacte na raiz do projeto:

   ```powershell
   Compress-Archive -Path models\*.joblib, models\*.json -DestinationPath modelos.zip -Force
   (Get-FileHash modelos.zip -Algorithm SHA256).Hash     # anote: vai em ASSESSOR_MODELS_SHA256
   ```

2. No GitHub: **Releases → Draft a new release**. Crie uma tag, ex. `modelos-v1`, e anexe o
   `modelos.zip`. A URL fica:
   `https://github.com/ScriptPedro/TCS-CLAUDE/releases/download/modelos-v1/modelos.zip`

> O repositório é público, então quem tiver a URL baixa os modelos. Eles não contêm os dados do
> Kaggle nem dados de usuários, mas não anexe nada além dos quatro arquivos.

## 2. Subir a API e o banco no Render

1. Crie uma conta em <https://render.com> (dá para entrar com o GitHub, sem cartão).
2. **New → Blueprint**, escolha o repositório `ScriptPedro/TCS-CLAUDE` e o branch (`main`).
3. O Render lê o `render.yaml` e pede os valores que não estão no arquivo:
   - `ASSESSOR_MODELS_URL`: a URL do passo 1;
   - `ASSESSOR_MODELS_SHA256`: o hash do passo 1 (pode deixar vazio, mas é recomendado: os
     `.joblib` executam código ao carregar).
4. **Apply**. O build do Docker leva alguns minutos. No fim, abra
   `https://<nome>.onrender.com/api/saude`: deve responder `{"modelos": true, ...}`.

O nome do serviço é `assessor-api`. Se estiver ocupado, o Render acrescenta um sufixo ao endereço.
Use o endereço que aparece no painel.

## 3. Criar o primeiro administrador

O cadastro público só cria usuários comuns. O plano grátis não tem *Shell* no Render, então rode o
comando no seu computador, apontando para o banco do Render:

1. No painel do banco `assessor-db`: **Connect → External Connection** e copie a *External Database
   URL*.
2. Na raiz do projeto, com o `.venv` ativo:

   ```powershell
   $env:ASSESSOR_DATABASE_URL = "<External Database URL>"
   python -m api.usuarios criar-admin
   Remove-Item Env:ASSESSOR_DATABASE_URL
   ```

A URL externa contém a senha do banco. Não a coloque em arquivos do repositório.

## 4. Publicar o front no GitHub Pages

1. No GitHub, em **Settings → Pages → Build and deployment → Source**, escolha **GitHub Actions**.
2. Em **Settings → Secrets and variables → Actions → Variables → New repository variable**, crie
   `API_URL` com o endereço da API, sem barra no fim (ex.: `https://assessor-api.onrender.com`).
3. O workflow roda a cada push na `main` que mexe em `frontend/`. Para rodar agora, use
   **Actions → Front no GitHub Pages → Run workflow**. O site fica em
   <https://scriptpedro.github.io/TCS-CLAUDE/>.

O workflow só aparece em *Actions* depois que `.github/workflows/pages.yml` estiver na `main`.

## Atualizar

- **Mudou o código da API:** o Render refaz o deploy sozinho a cada push no branch do Blueprint.
- **Mudou o front:** o workflow publica de novo a cada push na `main` em `frontend/`.
- **Retreinou os modelos:** crie uma nova release (`modelos-v2`), troque `ASSESSOR_MODELS_URL` e
  `ASSESSOR_MODELS_SHA256` em *Environment* e salve. O Render reinicia a API com os modelos novos.
- **Mudou o endereço do Pages** (outro dono ou domínio): ajuste `ASSESSOR_CORS_ORIGINS` no
  `render.yaml` (só esquema + host, sem `/TCS-CLAUDE`). Para várias origens, separe por vírgula.

## Problemas comuns

- **`/api/saude` com `"modelos": false`:** veja os *Logs* do serviço. A primeira linha diz se o
  download funcionou ("Modelos baixados…") ou por que falhou: URL errada, SHA-256 diferente ou
  `.zip` sem algum arquivo.
- **No site, "Não foi possível falar com o servidor":** a API está acordando. Espere um minuto e
  tente de novo. Se continuar, abra `<API>/api/saude` direto no navegador.
- **Erro de CORS no console do navegador:** `ASSESSOR_CORS_ORIGINS` não bate com a origem do site.
  Também pode ser a API fora do ar: o Render devolve a página de erro sem o cabeçalho de CORS.
- **Login responde 503 ("O banco de dados não respondeu"):** o Postgres grátis expirou ou está
  suspenso. Veja o painel do banco.
- **Página do Pages em branco:** confira se o build usou `VITE_BASE=/TCS-CLAUDE/` (o workflow já faz isso)
  e se a *Source* do Pages é **GitHub Actions**.
