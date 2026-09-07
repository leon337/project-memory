# Gate 2R — Remediação de fidelidade de input Linux/X11

Data: 2026-09-07
Host: `leo-N43SM`
Issue: #19
Candidato físico: `c7a5c12cb5c8dfdfaf6c2146565181455591eba7`

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

Foram adicionadas cinco regressões em `tests/test_desktop_focus.py` cobrindo leitura X11 do Caps Lock, transição verificada, normalização/restauração, restauração em exceção e fail-closed quando o estado é desconhecido.

Antes da implementação: 5/5 RED pelo comportamento ausente.
Depois da implementação:

- regressões Caps Lock: 5/5 PASS;
- `tests/test_desktop_focus.py`: 24/24 PASS;
- compilação `src + tests`: PASS;
- suíte integral: 411 testes PASS.

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

Task: `dc23248b-5932-4bcd-830b-1e4a7fcdbf85`.

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

## Resultado

**PASS — INPUT FIDELITY RESTAURADA NO CENÁRIO FÍSICO QUE HAVIA FALHADO.**

O Issue #19 só deve ser encerrado após merge e revalidação da `main`.
