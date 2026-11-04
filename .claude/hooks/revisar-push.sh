#!/usr/bin/env bash
# Antes de qualquer "git push" feito pelo Claude Code: mostra o que vai sair
# (branch, commits, arquivos) e força o pedido de autorização ao usuário.
# Só usa bash e git (funciona no Git Bash do Windows). Não lê a entrada do hook:
# o filtro "if" em .claude/settings.json garante que só roda para git push.
cd "${CLAUDE_PROJECT_DIR:-.}" 2>/dev/null || true

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if remoto=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null); then
  faixa="$remoto..HEAD"
else
  remoto="origin/$branch (ainda não existe no remoto)"
  base=$(git merge-base HEAD "$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || echo origin/main)" 2>/dev/null)
  faixa="${base:+$base..}HEAD"
fi

commits=$(git log --format='  %h  %an  %s' "$faixa" 2>/dev/null | head -30)
arquivos=$(git diff --stat "$faixa" 2>/dev/null | tail -40)
[ -z "$commits" ] && commits="  (nenhum commit novo; o push pode ser de outra branch ou um force push)"

resumo="REVISÃO DO PUSH
Branch local: $branch  →  remoto: $remoto

Commits que vão sair:
$commits

Arquivos alterados:
$arquivos

Para ver o diff completo antes de aprovar: git diff $faixa"

# JSON sem jq: escapa \ e ", e transforma quebras de linha em \n
json=$(printf '%s' "$resumo" | awk 'BEGIN{ORS=""} {gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); gsub(/\t/,"\\t"); if (NR>1) print "\\n"; print}')
printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"%s"}}\n' "$json" "$json"
