# Gate 2R — Remediação de fidelidade de input Linux/X11

Data: 2026-09-07
Host: `leo-N43SM`
Issue: #19
Candidato físico: `985fec485374cca0e57306ce7176cdfa652f27d9`

## Objetivo

Remediar o FAIL seguro do Gate 2 sem reduzir foco, FAILSAFE, Durable Journal, percepção independente ou autoridade do GoalVerifier.

## Investigação de causa raiz

O Gate 2 havia produzido `vALIDAE7\nE3\nO REAL NFA\nMERO 1` para o alvo `Validação real número 1`. A investigação separou os fatores:

1. Caps Lock ON + `type_text('Valida')` → readback `vALIDA`.
2. Caps Lock ON + `type_text('çãú')` → readback `E7\nE3\nFA\n`.
3. Caps Lock temporariamente OFF + `type_text('Valida')` → `Valida`.
4. Caps Lock temporariamente OFF + `type_text('çãú')` → `çãú`.
5. O estado original ON foi restaurado após os experimentos.

A alternativa `xdotool type --clearmodifiers` foi descartada: falhou ao encontrar sequência multibyte e deixou Caps Lock OFF, exigindo restauração explícita.

Conclusão: Caps Lock era a causa raiz comum do desvio ASCII e da falha do protocolo Unicode nesta sessão X11.

## TDD

Foram adicionadas seis regressões em `tests/test_desktop_focus.py` cobrindo leitura X11 do Caps Lock, transição verificada, normalização/restauração, restauração em exceção e fail-closed quando o estado é desconhecido.

Antes da implementação inicial: 5/5 RED pelo comportamento ausente. Na revisão pré-merge foi encontrado um risco adicional: a normalização para OFF acontecia antes do `try`, podendo impedir a restauração caso a própria normalização falhasse após alterar o estado. Um sexto teste foi visto RED nesse cenário e o hardening moveu a normalização para dentro do bloco protegido por `finally`.
Depois da implementação/hardening:

- regressões Caps Lock: 6/6 PASS;
- `tests/test_desktop_focus.py`: 25/25 PASS;
- compilação `src + tests`: PASS;
- suíte integral: 412 testes PASS.

## Implementação

`PyAutoGuiDesktopBackend.type_text` agora:

- consulta Caps Lock via `xset q` numa sessão com `DISPLAY`;
- falha fechado se o estado não puder ser determinado;
- quando ON, usa `xdotool key Caps_Lock` para normalizar temporariamente para OFF e verifica a transição;
- executa o caminho ASCII/Unicode já existente;
- restaura o estado inicial em `finally` e verifica a restauração;
- não usa clipboard.

Nenhum contrato de planner, GoalVerifier, journal, lease, Policy, Emergency Stop ou readback foi alterado.

## Verificação física direta

Com Caps Lock ON antes da ação, o backend escreveu `Validação real número 1` e o readback AT-SPI retornou exatamente o mesmo texto. Caps Lock estava ON novamente ao final.

## Smoke E2E

Foi executado uma única vez `scripts/validate_home_v4_1_physical.py` no candidato.

Task: `c77e553d-f787-421e-b90f-54571b878f4e`.

Resultado observado:

```text
PASS: Central, Robô e Desktop prontos; emergência normal
PASS: fronteira Host/Origin/status validada
PASS: conversa isolada respondeu via cloudflare/@cf/meta/llama-3.1-8b-instruct-fast
PASS: GoalVerifier autorizou succeeded com verified=true
PASS: readback AT-SPI exato: 'Validação real número 1'
PASS_GATE: HOME_V4_1_PHYSICAL
```

A task terminou `succeeded`, `goal_completed=true`, `verified=true`, attempts=1. `open_app` e `type_text` ficaram `acknowledged`; não houve retry/replay. Caps Lock permaneceu ON após o smoke.

## Cleanup

Xed, Painel, Central e Robô iniciados para a validação foram encerrados. Portas 8000/8765 ficaram livres e Caps Lock permaneceu no estado inicial ON.

## Pós-merge — isolamento de teste com DISPLAY real

A primeira execução de `validar-robo` em `main` retornou `1 failed, 411 passed`. A falha estava em `test_non_editor_app_with_confirmed_focus_can_receive_keyboard`: o teste mockava `shutil.which` para expor apenas `firefox` e `xdotool`; com `DISPLAY=:0`, isso escondia `xset` e fazia o novo fail-closed de Caps Lock interromper corretamente a digitação simulada.

O follow-up foi restrito ao teste: `_caps_lock_enabled` foi fixado como `False` naquele cenário porque o objetivo do teste é validar foco/teclado em aplicativo não-editor, não integração X11 de lock state. Nenhum código de produção foi alterado. Com o isolamento corrigido, `tests/test_desktop_focus.py` passou 25/25 e a suíte integral, executada com `DISPLAY=:0` e Caps Lock real ON, passou `412 passed, 1 warning`.

## Resultado

**PASS — INPUT FIDELITY RESTAURADA NO CENÁRIO FÍSICO QUE HAVIA FALHADO.**

O Issue #19 só deve ser encerrado após merge e revalidação da `main`.
