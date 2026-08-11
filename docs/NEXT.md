# NEXT

## 1. Repetir exatamente o smoke físico `after_executed`

O host Linux/X11 já foi atualizado com a correção do issue #14 e o `validar-robo` terminou em `RESULTADO: PRONTO PARA TESTE FÍSICO`, com `399 passed`.

Fechar o Xed anterior. Em um terminal do projeto, armar `falha-robo armar after_executed`. Em seguida, pelo Painel → Central → Robô, executar exatamente `Abra o editor de texto`.

Quando o fault injection encerrar o Robô após `executed`, manter o editor aberto e religar somente o Robô pelo Painel. Não reabrir o editor manualmente e não alterar o foco de propósito além do necessário para religar o Robô.

Critérios de PASS: a mesma task é recuperada sem segunda emissão física de `open_app`; a percepção independente encontra o Xed já existente mesmo se Painel/Brave estiver ativo; GoalVerifier conclui de forma coerente com o estado real. Receipt recuperado não pode ser usado sozinho como prova.

## 2. Se o reteste passar, registrar a evidência e fechar o issue #14

Registrar task id, tentativa/reclaim, journal state, ausência de segunda abertura física, observação independente e verdict final. Só então fechar o issue #14 e atualizar STATUS.

## 3. Somente após PASS, continuar os checkpoints restantes

Validar `after_prepare`, `after_in_flight`, `before_ack` e `after_ack` um por vez. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.