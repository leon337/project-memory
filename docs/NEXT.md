# NEXT

## 1. Corrigir o issue #14 de recovery/verificação após `executed`

O checkpoint `after_executed` comprovou zero replay físico de `open_app`, porém a mesma task recuperada terminou `failed` com `GoalExecutionFailed: RuntimeError: Xed abriu, mas a capacidade não foi observada`, mesmo com o editor ainda aberto.

Corrigir a percepção independente usada após receipt recuperado para que o sistema consiga reconhecer o aplicativo/janela já existente sem reemitir `open_app`. Preservar GoalVerifier como única autoridade de conclusão e manter ExecutionReceipt insuficiente como prova de efeito.

Adicionar regressão automatizada e exigir CI completo verde.

## 2. Atualizar o host e repetir exatamente o smoke físico `after_executed`

Depois da correção publicada, executar `atualizar-robo && validar-robo` e repetir o mesmo cenário no Linux/X11 real. Critérios: nenhuma segunda emissão física de `open_app`, percepção independente reconhece o estado real e a task termina de forma coerente com o objetivo já satisfeito.

## 3. Somente após PASS, continuar os checkpoints restantes

Validar `after_prepare`, `after_in_flight`, `before_ack` e `after_ack` um por vez. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem prova no host.