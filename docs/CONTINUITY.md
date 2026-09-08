# Continuidade — overlay do project-memory

## Escopo

Este arquivo complementa, sem duplicar, o protocolo universal `docs/protocols/MCF-PROTOCOLO-CONTINUIDADE-MULTI-IA-V1.2.md` do repositório `leon337/multiagent-collaboration-framework`.

Ele define apenas como as regras universais resolvem as fontes e o estado deste projeto. Não altera o runtime do Robô, não muda a autoridade do GoalVerifier e não autoriza implementação de `PM-UNIVERSAL-OPERATOR-001`.

## Autoridade por domínio

- identidade e registro do projeto: registry do MCF;
- verdade técnica verificável do projeto: `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` e `docs/NEXT.md`;
- snapshot rápido: `.mcf/project-capsule.yaml`;
- estado físico/local atual: observação LIVE do host `leo-N43SM`, quando a missão depender dele;
- histórico e verdade da execução de tasks: Central SQLite e Durable Action Journal;
- memória de chat: não autoritativa.

Estado Git remoto e estado local/live são objetos distintos. Um SHA remoto, um working tree local e o estado runtime não substituem silenciosamente uns aos outros.

## Bootstrap deste projeto

Depois de o protocolo universal resolver `project-memory` no registry, carregar a capsule e os quatro entrypoints canônicos, inspecionar trabalho aberto e comparar remoto/local. Se a tarefa depender do notebook ou de uma execução, reobservar o host e/ou SQLite/Journal antes de decidir.

Gate 2R já é histórico `PASS` e não deve ser repetido como bootstrap. A continuação parte do próximo gate executável sustentado pelas fontes atuais.

## Estado do Gate 3

A arquitetura do Gate 3 foi autorizada e o lado MCF está no draft PR #201. Este overlay está materializado neste branch, mas Gate 3 permanece `CANONICALIZATION_PENDING` até os PRs pareados serem persistidos/mesclados conforme a governança e o resultado ser objetivamente verificado.

Aprovação humana não produz evidência `PASS` nem estado `CANONICAL` por si só. Enquanto a canonicalização cross-repo não terminar, este documento é proposta de branch, não baseline vigente em `main`.
