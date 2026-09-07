# Gate 2 — Smoke físico mínimo Linux/X11

Data: 2026-09-07
Host: `leo-N43SM`
Base executada: `5fda7f24f8b828a7d0557fd2d7ff1defc37ad3a7`
Issue de remediação: #19

## Objetivo

Reexecutar uma única vez o ciclo físico canônico Painel → Central → Robô → Goal Runtime → evidência independente → GoalVerifier, sem iniciar nova implementação operacional.

## Preflight

- Linux Mint 22.3 / XFCE / X11 `:0`;
- layout XKB `br`;
- locale do XFCE `pt_BR.UTF-8`;
- fault injection `DESARMADO`;
- Emergency Stop `active=false`;
- nenhuma janela/processo Xed aberto antes do teste;
- Central, Robô e Painel iniciados separadamente;
- `/api/status`: Central online, Robô online, desktop habilitado e emergência inativa.

## Validador físico

Foi executado uma única vez:

```text
.venv/bin/python scripts/validate_home_v4_1_physical.py
```

O preâmbulo do validador passou:

```text
PASS: Central, Robô e Desktop prontos; emergência normal
PASS: fronteira Host/Origin/status validada
PASS: conversa isolada respondeu via cloudflare/@cf/meta/llama-3.1-8b-instruct-fast
```

Task criada:

`d0a7fb12-64ea-4eba-9033-9a5b770a8d5a`

Objetivo físico esperado:

`Validação real número 1`

## Resultado observado

O Xed abriu em uma nova janela e a ação de digitação foi emitida. O readback AT-SPI posterior retornou texto divergente:

```text
vALIDAE7
E3
O REAL NFA
MERO 1
```

A task terminou corretamente em `failed`:

```text
GoalExecutionFailed: GoalVerifier recusou conclusão; critérios pendentes: text_present
```

Não houve falso `succeeded`.

## Durable Journal

Na única tentativa da task:

- `open_app`: `acknowledged`, receipt `verified=true`;
- `type_text`: `acknowledged`, receipt `verified=true`;
- `type_text.input_method`: `linux-unicode-input`;
- `type_text.characters`: 23;
- readback independente: `verified=true`, source `at-spi`, valor divergente;
- attempts: 1;
- nenhum replay físico foi observado.

Isso confirma a separação entre receipt de execução e prova de objetivo: o backend executou ações, mas o GoalVerifier recusou conclusão porque o estado final não correspondeu ao critério.

## Diagnóstico delimitado

### Caps Lock

A sessão tinha `Caps Lock: on`. Isso é consistente com a inversão `Valida` → `vALIDA` quando a digitação sintética combina o estado real de Caps Lock com Shift para maiúsculas.

### Unicode

O método atual usa `Ctrl+Shift+U` + hexadecimal + `Enter` para caracteres não ASCII. No smoke, o modo Unicode não foi aceito: os códigos apareceram literalmente no editor. Os valores observados correspondem aos codepoints:

- `ç` → `e7`;
- `ã` → `e3`;
- `ú` → `fa`.

Os `Enter` da sequência viraram quebras de linha.

### Cobertura existente

`tests/test_desktop_focus.py::test_type_text_preserves_unicode_with_linux_codepoint_input` usa `FakeGui`. Ele comprova que a sequência de teclas é emitida, mas não prova o resultado físico em X11 real, layout `br`, estado de Caps Lock ou aceitação do método Unicode pelo aplicativo/toolkit.

## Cleanup

Após o FAIL:

- não houve retry automático;
- Xed do teste foi encerrado sem salvar;
- Painel, Central e Robô iniciados para o smoke foram encerrados;
- portas 8765/8000 ficaram livres novamente.

## Resultado do Gate 2

**FAIL SEGURO — INPUT FIDELITY NÃO COMPROVADA NO ESTADO ATUAL.**

O GoalVerifier e o readback independente funcionaram corretamente e impediram falso sucesso. O próximo trabalho deve ser uma remediação controlada do Issue #19, seguida de regressões automatizadas e um novo smoke físico de uma rodada.

Nenhuma correção operacional foi implementada neste gate.
