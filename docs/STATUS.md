# STATUS

## Objetivo atual

Construir um operador digital local capaz de receber objetivos em linguagem natural, descobrir capacidades disponíveis, executar em ciclo fechado e só encerrar quando o resultado final estiver comprovado por evidências.

## Estado verificável agora

O `main` continua no commit `b7f79a0e4830d37d763a46b981497b52519781b8` com o MVP anterior estável.

O trabalho pesado do novo Goal Runtime está preservado na branch:

`codex/goal-runtime-wip`

Checkpoint inicial:

`f73abddc23b676c990755011621a3a4b1db7b4f7`

Correção P0 de grounding de URL:

`5894f98c0a1004a76bc10326a04a58e08b9807e0`

A branch contém a implementação e os testes da missão sem incluir PNGs, PDFs, arquivos pessoais ou `egg-info`.

## Arquitetura nova implementada na branch WIP

```text
pedido
→ claim + lease
→ contexto operacional curto
→ interpretação local tipada ou decomposição estruturada por provider
→ GoalContract / GoalRunState
→ Capability Resolver
→ Policy Layer
→ executor físico
→ ExecutionReceipt
→ percepção independente
→ EvidenceRecord
→ GoalVerifier
→ continuar/falhar/succeeded
```

Componentes principais:

- `src/context_anchor/goal_execution.py` — orquestrador universal de Goal Runs;
- `src/context_anchor/capabilities.py` — resolução de capacidades para aplicativos instalados;
- `src/context_anchor/goal_interpreter.py` — interpretação tipada e fail-closed para cobertura incompleta;
- `src/context_anchor/session_context.py` — memória operacional curta com proveniência/TTL;
- `src/context_anchor/lease.py` — heartbeat e proteção de posse da task;
- `src/context_anchor/redaction.py` — sanitização de resultados/logs/contexto;
- `src/context_anchor/goal_runtime.py` — contratos, evidências, budgets e `GoalVerifier`.

`src/context_anchor/local_agent.py` encaminha todo comando para `execute_goal()` na branch WIP.

## Regra de conclusão implementada

- `ExecutionReceipt` registra execução, mas não prova sozinho o efeito do objetivo;
- critérios obrigatórios precisam de observação/readback compatível;
- subobjetivos dependentes precisam estar satisfeitos;
- contratos sem critérios obrigatórios não concluem;
- `finish`/planner não possuem autoridade para encerrar objetivo incompleto;
- `GoalVerifier` é a autoridade final para `SUCCEEDED`.

## P0 de cobertura de URL — corrigido

O caso:

`Abra o Brave, acesse example.com e pesquise gatos`

podia perder a URL explícita e virar busca em outro mecanismo.

O commit `5894f98c0a1004a76bc10326a04a58e08b9807e0` corrigiu isso:

- navegador nomeado sem site explícito continua fast path;
- Google/Bing/DuckDuckGo explícitos continuam fast path;
- site explícito não reconhecido como mecanismo de busca vai para `GENERIC`/fail-closed antes de ação física;
- teste de runtime exige `executor.executed == []` no caso incorreto.

O Codex reportou `10 passed` nos testes focados.

## Testes automatizados

No checkpoint anterior à correção P0, o Codex reportou suíte local completa:

`333 passed, 1 warning`

Depois da correção P0 foram reportados `10 passed` nos testes diretamente relacionados.

Ainda não existe execução de GitHub Actions para a branch WIP; a suíte completa deve ser repetida antes do merge.

## Bateria física integrada — 2026-08-09

Os testes abaixo foram executados pelo fluxo real Painel → Central → Robô usando o código da branch WIP no commit de código `5894f98c0a1004a76bc10326a04a58e08b9807e0`. O `git pull` posterior trouxe somente atualizações documentais, portanto não invalida esses resultados físicos.

### 1. Editor + Unicode — PASS

Pedido:

`Abra o editor de texto e escreva Olá mundo`

Resultado observado:

- editor real abriu;
- `Olá mundo` apareceu exatamente;
- Painel marcou `succeeded`;
- logs mostraram Goal Runtime concluído.

### 2. VS Code por alias — PASS

Pedido:

`Abra o VS Code`

Resultado observado:

- Visual Studio Code abriu fisicamente;
- Painel marcou `succeeded`.

### 3. Necessidade vaga de cálculo — PASS

Pedido:

`Preciso fazer algumas contas.`

Resultado observado:

- calculadora real abriu;
- Painel marcou `succeeded`.

Esse teste comprova resolução da necessidade para capability de cálculo; não comprova ainda execução de uma operação matemática solicitada.

### 4. Necessidade natural de informação — PASS

Pedido:

`Quero saber o significado do nome Josiel.`

Resultado observado:

- busca correta foi aberta;
- página apresentou resultados sobre o significado de Josiel;
- Painel marcou `succeeded`.

### 5. Regressão crítica pesquisa → título → editor — PASS

Pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Resultado observado:

- DuckDuckGo pesquisou apenas `inteligência artificial`;
- resultados reais foram exibidos;
- primeiro resultado observado foi `Inteligência artificial - Wikipédia, a enciclopédia livre`;
- editor real abriu;
- exatamente esse título foi escrito no editor;
- Painel marcou `succeeded`.

Esse teste elimina fisicamente o falso PASS histórico para esse caso específico.

### 6. Condicional example.com — FAIL com progresso parcial

Pedido:

`Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".`

Resultado observado:

- `example.com` abriu e estava acessível;
- o branch acessível foi escolhido;
- editor abriu;
- texto final ficou incorreto, visualmente dividido como `SITE ACESSO` / `VEL` em vez de `site acessível`;
- task terminou `failed`;
- log: `GoalVerifier recusou conclusão: critérios pendentes: text_present`.

Classificação: execução parcial correta, conclusão final FAIL. O verifier evitou falso `succeeded`.

### 7. Informações sobre São Lourenço da Mata — FAIL de percepção estruturada

Pedido:

`Pesquise informações sobre São Lourenço da Mata.`

Resultado observado:

- DuckDuckGo abriu com a consulta correta;
- resultados reais sobre São Lourenço da Mata ficaram visíveis;
- task terminou `failed`;
- log: `RuntimeError: duckduckgo não produziu resultados estruturados verificáveis`.

Classificação: ação de busca fisicamente útil, mas critério de percepção/evidência não foi satisfeito.

### 8. Contexto entre tasks com `lá` — FAIL

Pedido após o teste 7:

`Agora pesquise a previsão do tempo de lá.`

Resultado observado:

- `lá` não foi resolvido para São Lourenço da Mata;
- a consulta física virou `a previsão do tempo de inteligência artificial`;
- task terminou `failed`.

Causa observável provável:

- o teste 7 falhou, portanto seu contexto não foi publicado;
- o `SessionContext` caiu para um artefato anterior de `SUBJECT` (`inteligência artificial`);
- o fallback de `lá` para `SUBJECT` mostrou-se semanticamente inseguro.

Esse comportamento deve ser corrigido para falhar fechado ou usar apenas um artefato compatível com referência locativa, em vez de substituir `lá` por assunto arbitrário.

## Situação da autonomia física após a bateria

PASS confirmados: 5.

FAIL confirmados: 3.

Os FAILs atuais estão concentrados em:

1. escrita/readback da string acentuada no branch condicional;
2. extração/percepção estruturada de resultados do DuckDuckGo em busca informacional;
3. resolução contextual de `lá` quando não existe `LOCATION` válido da task anterior.

Importante: nos testes 6 e 7 o sistema falhou em vez de declarar sucesso sem evidência, o que confirma que o GoalVerifier está protegendo contra falso `succeeded` nesses casos.

## Providers

O modo multi continua com Z.AI/GLM, Google Gemini e Cloudflare Workers AI. Cloudflare ainda depende de `Account ID` no ambiente real. Z.AI/Gemini já apresentaram 429 em testes anteriores; fast paths e capabilities locais continuam importantes para preservar quota.

## Controles preservados

- Emergency Stop persistente;
- FAILSAFE físico;
- proteção de foco;
- Policy Layer;
- `shell=False`;
- leases da Central;
- credenciais fora de código/Git/logs;
- Painel/Central em localhost por padrão.

## Situação de conclusão

A missão **não está concluída** e a branch WIP **não deve ser mergeada em `main` ainda**.

O próximo trabalho é corrigir os três FAILs físicos acima, repetir a bateria afetada e então executar suíte completa/checks antes de qualquer promoção para `main`.
