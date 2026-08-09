# CODEX GOAL RUNTIME MISSION

## Missão

Integrar a fundação de `src/context_anchor/goal_runtime.py` ao runtime real do Robô e continuar trabalhando até que o operador seja orientado a objetivos de verdade, com testes automatizados e validações físicas no Linux/X11.

Esta missão não termina em `pytest` verde. Ela termina quando os critérios físicos obrigatórios abaixo forem atingidos ou quando existir um bloqueio externo comprovável que o código não possa resolver sozinho.

## Fonte de verdade

Antes de modificar, ler nesta ordem:

1. `docs/STATUS.md`
2. `docs/ARCHITECTURE.md`
3. `docs/DECISIONS.md`
4. `docs/NEXT.md`

Depois ler este arquivo. Não é necessário fazer uma leitura ampla do repositório antes de começar; os arquivos prioritários estão listados abaixo.

## Estado preparado

Já existe uma fundação isolada em:

- `src/context_anchor/goal_runtime.py`
- `tests/test_goal_runtime_contract.py`

Contratos existentes:

- `GoalContract`
- `GoalCriterion`
- `GoalSubgoal`
- `GoalRunState`
- `EvidenceRecord`
- `EvidenceKind`
- `GoalVerdict`
- `GoalVerifier`

Regra já estabelecida: `ExecutionReceipt` não é evidência suficiente de conclusão do objetivo. `succeeded` só pode existir quando todos os critérios obrigatórios estiverem comprovados por evidência apropriada.

## Problema estrutural atual

`src/context_anchor/local_agent.py` possui três semânticas diferentes de conclusão:

1. comando determinístico simples executa uma ação e retorna diretamente;
2. `plan_local_sequence()` executa etapas e define `goal_completed=True` ao final da sequência;
3. loop por IA aceita `action=finish` do planner como encerramento.

Isso permitiu um falso `succeeded` físico no pedido:

`Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Na prática apenas a pesquisa foi aberta. O primeiro resultado não foi lido, o editor não foi aberto e o título não foi escrito.

## Princípio obrigatório

Todo pedido deve passar pelo mesmo `Goal Run`, inclusive fast paths determinísticos.

Fast path continua existindo, mas apenas como forma barata de selecionar/produzir próximos steps. Ele não pode decidir sozinho que o objetivo terminou.

Fluxo obrigatório:

```text
objetivo do usuário
→ GoalContract
→ GoalRunState
→ próximo subobjetivo
→ selecionar step/skill
→ Policy Layer
→ execução
→ ExecutionReceipt
→ observação independente quando necessária
→ EvidenceRecord
→ GoalVerifier
→ incompleto: continuar/replanejar
→ completo: succeeded
```

Nenhum planner, executor ou fast path pode persistir `succeeded` diretamente.

## Arquivos prioritários

Começar por estes; ler outros apenas quando uma dependência concreta exigir:

- `src/context_anchor/goal_runtime.py`
- `src/context_anchor/local_agent.py`
- `src/context_anchor/planner.py`
- `src/context_anchor/policy.py`
- `src/context_anchor/actions.py`
- `src/context_anchor/desktop.py`
- `src/context_anchor/store.py`
- `src/context_anchor/control_plane.py`
- `src/context_anchor/schemas.py`
- `tests/test_goal_runtime_contract.py`
- `tests/test_goal_loop.py`
- `tests/test_policy.py`
- `tests/test_desktop_resolution.py`

## Trabalho obrigatório

### 1. Universalizar o Goal Run

Refatorar `execute_command()` para que todos os caminhos — determinístico simples, sequência determinística e IA — criem/atualizem um `GoalRunState`.

Não manter um caminho capaz de retornar sucesso fora do `GoalVerifier`.

Preservar os fast paths atuais como otimizações internas.

### 2. Criar Goal Contracts reais

Para os casos determinísticos já conhecidos, criar contratos sem usar provider externo.

Exemplos mínimos:

- abrir aplicativo;
- abrir URL;
- pesquisar;
- abrir editor + escrever texto;
- navegador + site;
- navegador + mecanismo de busca + consulta.

Cada contrato precisa ter critérios de conclusão explícitos.

### 3. Separar receipt de evidence

O retorno do executor deve ser tratado como recibo técnico.

Para critérios que exigem comprovação do estado final, coletar observação independente.

Exemplos:

- `open_app` pode produzir receipt de processo/janela, mas o critério é comprovado pela observação da janela/aplicativo esperado;
- `open_url` pode produzir receipt de navegação, mas objetivos de leitura/pesquisa exigem observar conteúdo relevante;
- `type_text` não deve provar sozinho que o texto correto ficou presente na superfície editável.

### 4. Browser perception estruturada

Estender o executor/browser para expor observações úteis sem screenshot quando Playwright já possui dados estruturados.

Prioridade mínima:

- URL atual;
- título;
- texto útil da página;
- links/resultados relevantes;
- extração do primeiro resultado de busca com título e URL.

Criar capacidade suficiente para o teste físico de pesquisa → primeiro resultado → editor.

### 5. Capability Resolver

Não resolver necessidade humana diretamente como executável inventado.

Introduzir uma camada pequena de capacidades, por exemplo:

- `text.edit`
- `calculate`
- `web.search`
- `web.read`
- `browser.navigate`
- `code.edit`

Resolver capacidade para ferramenta realmente disponível no ambiente.

Usar descoberta local quando possível (`PATH`, executáveis, `.desktop`/metadados disponíveis) antes de depender de alias fixo.

Casos obrigatórios:

- `Visual Studio Code` e `VS Code` convergem para a mesma ferramenta;
- `Preciso fazer algumas contas` não pode tentar um `calc` inexistente se há uma calculadora instalada disponível;
- `Quero fazer uma anotação` deve poder escolher uma ferramenta com capacidade de edição de texto.

### 6. Interpretação/decomposição semântica

Usar IA quando a intenção não for inequívoca localmente, mas a IA deve produzir representação de objetivo/subobjetivos/capacidades/critérios — não apenas uma ação livre.

Evitar criar regex específico para cada frase do baseline.

Providers continuam intercambiáveis e com fallback.

### 7. Replanning e progresso

Ao falhar uma estratégia recuperável, tentar alternativa coerente sem repetir indefinidamente.

Implementar pelo menos:

- step budget;
- retry budget por estratégia;
- detecção simples de falta de progresso/repetição;
- não repetir ação física já executada apenas por troca/falha de provider.

FAILSAFE, parada de emergência e proteção de foco continuam interrompendo normalmente e não devem ser contornados.

### 8. Contexto operacional curto

Permitir continuidade tipada entre tasks para referências como:

- `agora`;
- `lá`;
- `nesse navegador`;
- `nesse site`;
- `aquele resultado`.

Não usar histórico gigante de conversa. Persistir apenas estado operacional/artefatos referenciáveis, com origem e timestamp quando apropriado.

## Critérios físicos obrigatórios

O trabalho só pode ser considerado concluído depois de testar no computador real, pelo Painel/Robô, e registrar evidências.

### A. Regressões que devem continuar PASS

1. `Abra o editor de texto e escreva Olá mundo`
   - editor abre;
   - texto correto, incluindo acento;
   - objetivo comprovado;
   - `succeeded`.

2. `Abra o navegador e acesse o site globo.com`
   - site abre;
   - URL/estado observado compatível;
   - `succeeded`.

3. `Abra o navegador brave e acesse o site google.com e pesquise São Lourenço da Mata`
   - Brave abre;
   - pesquisa correta;
   - `succeeded`.

### B. Linguagem natural/autonomia

4. `Abra o VS Code`
   - VS Code realmente abre;
   - `succeeded`.

5. `Preciso fazer algumas contas.`
   - sistema escolhe autonomamente uma capacidade/ferramenta adequada disponível;
   - não exige nome de aplicativo;
   - `succeeded` apenas após comprovação do objetivo operacional definido.

6. `Quero fazer uma anotação. Abra alguma coisa onde eu possa escrever.`
   - sistema escolhe autonomamente uma ferramenta de edição disponível;
   - superfície apropriada aberta;
   - `succeeded`.

7. `Quero saber o significado do nome Josiel.`
   - sistema interpreta como objetivo informacional;
   - pesquisa/consulta é realizada sem o usuário prescrever navegador ou mecanismo;
   - informação/resultado relevante é observado;
   - conclusão não depende apenas de uma URL aberta.

### C. Caso crítico que antes produziu falso sucesso

8. `Pesquise inteligência artificial e depois abra um editor de texto e escreva o título do primeiro resultado.`

Obrigatório comprovar, em ordem lógica:

- pesquisa apenas pelo assunto correto;
- resultados observados;
- primeiro resultado identificado;
- título extraído como artefato;
- editor aberto;
- título escrito no editor;
- leitura/observação final suficiente para comprovar que o texto esperado está presente;
- somente então `succeeded`.

Se qualquer subobjetivo faltar, a task não pode terminar `succeeded`.

### D. Condicional real

9. `Verifique se example.com está acessível. Se estiver, abra um editor e escreva "site acessível". Se não estiver, escreva "site indisponível".`

Obrigatório:

- observar a condição;
- materializar/selecionar apenas o branch correto;
- executar o branch;
- verificar o texto final;
- `succeeded` somente depois da evidência.

### E. Contexto entre tasks

10. Executar primeiro uma pesquisa sobre `São Lourenço da Mata` e depois, em nova task:

`Agora pesquise a previsão do tempo de lá.`

Obrigatório resolver `lá` para o contexto anterior sem exigir repetição manual do local.

## Testes automatizados obrigatórios

Além da suíte já existente, criar regressões para:

- nenhum `ExecutionReceipt` isolado completar critério;
- planner `finish` não poder concluir Goal com critério pendente;
- fast path parcial não poder descartar o restante de pedido composto;
- todos os caminhos de `execute_command()` passarem pelo mesmo fechamento/verifier;
- capability resolver convergir `VS Code`/`Visual Studio Code`;
- capacidade `calculate` escolher ferramenta realmente disponível/mocada;
- extração estruturada do primeiro resultado em fixture HTML;
- dataflow de artefato: título extraído → texto enviado ao editor;
- branch condicional true e false;
- step/retry budget e detecção de repetição;
- fallback de provider não repetir ação física anterior.

Rodar a suíte completa antes de declarar conclusão.

## Métricas que devem aparecer no resultado/log

Por Goal Run, registrar sem segredos:

- goal id/task id;
- status;
- número de steps;
- subobjetivos satisfeitos/pendentes;
- critérios satisfeitos/pendentes;
- providers usados/fallbacks;
- retries/estratégias;
- motivo de conclusão/falha.

Não registrar credenciais nem conteúdo sensível desnecessário.

## Restrições de escopo

Não gastar tempo agora com:

- redesign do Painel;
- WhatsApp/Telegram/Instagram;
- câmera;
- publicação remota;
- múltiplos agentes/personas;
- reescrita de Central/Painel;
- visão multimodal como primeira solução de percepção.

Preservar:

- Painel/Central/Robô separados;
- SQLite/fila/leases;
- Policy Layer;
- emergency stop;
- FAILSAFE;
- proteção de foco;
- Unicode;
- multi-provider/fallback;
- fast paths úteis.

## Modo de trabalho exigido

Trabalhar em loop até atingir os critérios:

```text
inspecionar causa concreta
→ alterar código
→ teste específico
→ suíte relevante
→ teste físico quando necessário
→ observar resultado real
→ se falhar, diagnosticar e corrigir
→ repetir
```

Não parar para pedir aprovação entre correções normais. Só interromper por bloqueio que realmente exige ação humana, credencial inexistente, decisão de produto não determinada ou risco de destruir dados do usuário.

Não declarar conclusão baseado apenas em testes mockados. Para os critérios A–E, executar fisicamente no ambiente Linux/X11 ao qual o Codex possui acesso.

## Encerramento obrigatório

Antes de encerrar:

1. suíte completa verde;
2. testes físicos A–E executados e classificados honestamente;
3. nenhum falso `succeeded` conhecido;
4. `git diff --check`;
5. revisar diff;
6. commit/push das alterações corretas;
7. confirmar `main` remoto;
8. atualizar os quatro arquivos de memória relevantes;
9. deixar `docs/NEXT.md` com no máximo 3 itens reais restantes.

Se algum critério obrigatório continuar falhando, não declarar a missão concluída. Continuar corrigindo enquanto houver ação técnica possível no ambiente.