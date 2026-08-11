# NEXT

## 1. Executar crash físico `after_executed`

O smoke físico normal passou e o checkpoint `after_backend` também passou no host real: após restart/reclaim, a mesma task voltou como tentativa 2, encontrou `open_app` em estado durável `in_flight`, gerou `ActionReplayBlocked`, registrou `Replay físico bloqueado ... state=in_flight` e terminou `failed` sem nova emissão autorizada da ação.

Agora validar `after_executed`, onde a ação física já retornou e o journal já persistiu `executed`, mas o processo cai antes de a tarefa seguir normalmente. O teste deve usar uma ação com efeito visual fácil de comparar antes e depois do restart, evitando depender apenas de contagem de janelas.

## 2. Continuar os checkpoints restantes um por vez

Depois do PASS de `after_executed`, validar `after_prepare`, `after_in_flight`, `before_ack` e `after_ack`, sempre um cenário por vez. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem a prova no host.

## 3. Após o PASS físico completo, decidir a próxima evolução

Prioridades candidatas: implementar o primeiro item de `docs/VALIDATION-ROADMAP.md` (`teste-robo`, bateria guiada) ou expandir capabilities/replanning. Qualquer capability que precise repetir legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável explícita de contrato, sem reintroduzir contador implícito de retry.
