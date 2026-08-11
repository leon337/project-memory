# NEXT

## 1. Executar crash físico `after_backend`

O smoke físico normal no fluxo real Painel → Central → Robô passou: editor abriu, `JOURNAL-SMOKE-NORMAL-001` foi digitado exatamente uma vez, readback ficou `Confirmado`, GoalVerifier `SUCCEEDED` e a task terminou `succeeded`.

Agora armar `falha-robo armar after_backend` e executar um cenário físico que permita observar o efeito antes do crash. Esse checkpoint encerra o processo do Robô depois que o backend físico retorna e antes de o journal transicionar para `executed`, deixando a entrada durável em `in_flight`.

Após restart/reclaim, uma ação não repeat-safe nesse estado deve falhar fechada e não ser emitida novamente. A prova principal é ausência de duplicidade física.

## 2. Continuar os checkpoints de crash um por vez

Depois do PASS de `after_backend`, validar os demais checkpoints relevantes (`after_prepare`, `after_in_flight`, `after_executed`, `before_ack`, `after_ack`) sem executar a bateria toda de uma vez. Ação física, SQLite, journal, lease, reclaim e restart permanecem reais; fake/CI não substituem a prova no host.

## 3. Após o PASS físico, decidir a próxima evolução

Prioridades candidatas: implementar o primeiro item do `docs/VALIDATION-ROADMAP.md` (`teste-robo`, bateria guiada) ou expandir capabilities/replanning. Qualquer capability que precise repetir legitimamente duas ações físicas idênticas na mesma task deve fornecer identidade estável explícita de contrato, sem reintroduzir contador implícito de retry.
