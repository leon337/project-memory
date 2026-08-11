# NEXT

## 1. Publicar a correção do issue #14 e atualizar o host

Finalizar revisão/CI do PR #15 `PM-DURABLE-JOURNAL-RECOVERY-OBS-001`, integrar na `main` somente com CI verde e manter o issue #14 aberto até prova física.

Depois do merge, no host Linux/X11 já bootstrapado executar `atualizar-robo && validar-robo`. Só avançar se a validação terminar limpa em `RESULTADO: PRONTO PARA TESTE FÍSICO`.

## 2. Repetir exatamente o smoke físico `after_executed`

Fechar o Xed anterior, armar `falha-robo armar after_executed` e executar novamente `Abra o editor de texto` no fluxo Painel → Central → Robô. Após o crash, manter o editor aberto e religar somente o Robô.

Critérios de PASS: mesma task é recuperada sem segunda emissão física de `open_app`; a percepção independente encontra o Xed já existente mesmo se Painel/Brave estiver ativo; GoalVerifier conclui de forma coerente com o estado real. Receipt recuperado não pode ser usado sozinho como prova.

## 3. Somente após PASS, continuar os checkpoints restantes

Validar `after_prepare`, `after_in_flight`, `before_ack` e `after_ack` um por vez. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.