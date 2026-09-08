# NEXT

## 0. Gate 2R concluído — bloqueio de fidelidade de input removido

O Gate 2R isolou Caps Lock como causa raiz do FAIL físico do Issue #19, adicionou regressões, implementou normalização/restauração fail-closed no `type_text` e repetiu o smoke físico com GoalVerifier `verified=true` e readback AT-SPI exato. O artefato canônico é `artifacts/gates/GATE-02R-INPUT-FIDELITY-REMEDIATION-20260907.md`.

Não há nova ação de input pendente neste gate. A continuidade volta à prioridade estratégica abaixo; nova implementação operacional continua dependente de gate/autorização explícita.

## 1. Canonicalizar o Gate 3 e aceitar os PRs pareados

Substituir a aprovação do protocolo pela canonicalização coordenada entre o repositório do MCF e o project-memory: persistir os documentos universais e o overlay específico, verificar referências, autoridade por domínio e consistência entre os dois lados, e aceitar os PRs pareados (incluindo o draft do PR #201 quando pronto). Até essa aceitação conjunta, o estado permanece `CANONICALIZATION_PENDING`; aprovação isolada não torna o Gate 3 canônico.

O trabalho de produto da RC 3.5 e a implementação do primeiro slice permanecem depois do Gate 3. Esta etapa documental não autoriza implementação de `PM-UNIVERSAL-OPERATOR-001` nem alterações no runtime.

## 2. Retomar a RC física pelo drawer `Detalhes técnicos`

Os cinco estados críticos do protótipo (`executing`, `verifying`, `recovering`, falha segura e `succeeded`) já passaram na semântica visual observada. Depois de fechar o protocolo, abrir `Detalhes técnicos` e confirmar que capability, rota, journal, lease, recovery e referência de credencial aparecem somente nessa camada secundária, sem segredo real, sem sobreposição incorreta e com fechamento funcional por botão, backdrop e `Esc` quando aplicável.

## 3. Fechar responsividade/acessibilidade e decidir a RC 3.5 antes da quarta rodada

Depois do drawer, testar tamanhos de viewport e zoom diferentes, foco de teclado, contraste funcional, leitura sem depender apenas de cor e clareza das mensagens. A escala relativa (`rem`, `%`, `fr`, `clamp()`, `minmax()` e unidades de viewport) deve manter hierarquia e ausência de overflow indevido. Só depois aprovar, modificar ou rejeitar a RC 3.5; se aprovada, atualizar `ARCHITECTURE.md` e `DECISIONS.md` e então realizar a quarta rodada do primeiro slice Git/GitHub sandbox.
