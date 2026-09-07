# NEXT

## 0. Remediar o FAIL físico do Gate 2 — Issue #19

O smoke físico atual falhou de forma segura por fidelidade de input: Caps Lock estava ligado e o caminho `linux-unicode-input` materializou os codepoints Unicode como texto literal em vez de produzir `ç`, `ã` e `ú`. O GoalVerifier recusou o critério `text_present`, portanto não houve falso sucesso.

Antes de retomar qualquer expansão do Operador Universal ou repetir o smoke, abrir um gate de remediação explícito para o Issue #19. A correção deve preservar foco, FAILSAFE e clipboard do usuário, adicionar regressões para estado de modificadores/Unicode e só então autorizar um novo smoke físico de uma rodada com GoalVerifier `verified=true` e readback AT-SPI exato.

## 1. Aprovar ou ajustar o Protocolo de Continuidade v1.2 endurecido

A RC normal e a auditoria adversarial foram concluídas. A versão final candidata deve incorporar: autoridade por domínio entre os arquivos canônicos; separação entre estado remoto e local; dois eixos de estado (governança e evidência); canonicalização pendente quando LEANDRO aprova algo antes da persistência; detecção de conflito canônico e concorrência entre chats; revalidação de opções antigas; testes vinculados à versão/ambiente; PASS/FAIL por critério; `SEM OPÇÕES` limitado apenas à apresentação; e checkpoint documental por conjunto lógico, com registro imediato para decisão, FAIL crítico, mudança de direção ou gate.

O protocolo ainda não deve ser tratado como vigente até aprovação explícita de LEANDRO.

## 2. Retomar a RC física pelo drawer `Detalhes técnicos`

Os cinco estados críticos do protótipo (`executing`, `verifying`, `recovering`, falha segura e `succeeded`) já passaram na semântica visual observada. Depois de fechar o protocolo, abrir `Detalhes técnicos` e confirmar que capability, rota, journal, lease, recovery e referência de credencial aparecem somente nessa camada secundária, sem segredo real, sem sobreposição incorreta e com fechamento funcional por botão, backdrop e `Esc` quando aplicável.

## 3. Fechar responsividade/acessibilidade e decidir a RC 3.5 antes da quarta rodada

Depois do drawer, testar tamanhos de viewport e zoom diferentes, foco de teclado, contraste funcional, leitura sem depender apenas de cor e clareza das mensagens. A escala relativa (`rem`, `%`, `fr`, `clamp()`, `minmax()` e unidades de viewport) deve manter hierarquia e ausência de overflow indevido. Só depois aprovar, modificar ou rejeitar a RC 3.5; se aprovada, atualizar `ARCHITECTURE.md` e `DECISIONS.md` e então realizar a quarta rodada do primeiro slice Git/GitHub sandbox.
