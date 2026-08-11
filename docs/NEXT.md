# NEXT

## 1. Sincronizar a `main` local após a consolidação

A matriz física foi concluída e a documentação final foi publicada na `main` remota durante os testes. No host Linux/X11, manter o working tree limpo e executar `atualizar-robo` para trazer os commits documentais finais antes de restaurar os arquivos locais.

Critério: atualização segura por fast-forward, sem reset/clean/rebase e sem perder o stash temporário existente.

## 2. Restaurar o stash sem removê-lo ainda

Confirmar o stash com `git stash list` e inspecionar os nomes com `git stash show --include-untracked --name-only stash@{0}`. Em seguida usar `git stash apply stash@{0}` — não `pop` — para restaurar os arquivos mantendo o backup disponível.

Depois conferir `git status --short` e verificar visualmente que PDFs, imagens e demais arquivos locais esperados reapareceram. Se houver conflito, não apagar nem sobrescrever nada; preservar o stash e resolver explicitamente.

## 3. Remover o backup somente após conferência

Somente quando os arquivos restaurados estiverem confirmados, executar `git stash drop stash@{0}`. Depois registrar no STATUS que o ambiente local foi restaurado e definir a próxima fase de implementação; nenhum checkpoint físico do Durable Journal permanece pendente.
