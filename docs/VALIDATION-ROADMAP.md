# VALIDATION ROADMAP

Este documento registra melhorias aprovadas conceitualmente para o processo de atualização e testes, mas que **não fazem parte da implementação imediata** de `atualizar-robo`, `validar-robo` e `falha-robo`.

## Princípio de produto

O operador humano não deve precisar decorar detalhes de Git, PIDs, checkpoints ou sequência interna de processos para validar uma versão. A infraestrutura de teste deve reduzir o trabalho manual sem transformar testes físicos em simulação.

## R1 — `teste-robo`: bateria guiada de smoke físico

Objetivo: oferecer um único comando interativo para executar cenários físicos de forma sequencial e interromper a bateria no primeiro FAIL.

Escopo futuro:

- listar baterias disponíveis;
- preparar o cenário escolhido;
- informar exatamente uma ação humana por vez;
- armar/desarmar fault injection quando necessário;
- registrar início/fim e resultado de cada cenário;
- nunca declarar PASS sem evidência correspondente.

Critérios de aceite:

- usuário não precisa conhecer nomes internos de checkpoints;
- cada cenário apresenta `AÇÃO`, `PASS ESPERADO` e `RESULTADO`;
- FAIL interrompe a bateria e preserva evidências;
- mecanismo continua usando desktop/Playwright/SQLite reais.

Dependência: primeiro comprovar fisicamente que `falha-robo` e o Durable Journal funcionam no host Linux/X11 real.

## R2 — Integração da validação ao Painel

Objetivo: permitir iniciar validações e visualizar estado pelo Painel, sem transformar o Painel em autoridade de conclusão.

Escopo futuro:

- página/área de "Validação";
- estado da versão local e commit;
- resultado do último `validar-robo`;
- bateria física selecionável;
- indicação explícita quando um fault injection está armado;
- botão local para desarmar antes de operação normal.

Critérios de aceite:

- Painel mostra estado real, não decorativo;
- nenhuma validação perigosa começa silenciosamente;
- fault injection continua desarmado por padrão;
- GoalVerifier e Durable Journal mantêm suas autoridades atuais.

Dependências: R1 e desenho de UX específico.

## R3 — Pacote automático de evidências

Objetivo: produzir um bundle por execução de validação para comparação e auditoria.

Possível conteúdo:

- commit SHA;
- horário e host técnico não sensível;
- versões de Python e dependências essenciais;
- resumo do pytest;
- resultado de cada cenário físico;
- último evento de fault injection;
- logs correlacionados por task_id;
- screenshots somente quando explicitamente necessárias e sanitizadas.

Critérios de aceite:

- evidência técnica não é confundida com prova de objetivo;
- credenciais, texto sensível e targets brutos não entram no bundle;
- cada artefato possui proveniência e timestamp;
- execução pode ser reproduzida a partir do manifesto.

Dependência: R1.

## R4 — Histórico de validações no Painel

Objetivo: permitir comparar versões e detectar regressões físicas ao longo do tempo.

Escopo futuro:

- lista de execuções por commit;
- PASS/FAIL por cenário;
- diferenças de ambiente;
- acesso aos bundles de evidência;
- filtros por capability e tipo de falha.

Dependências: R2 + R3.

## R5 — Matriz de ambientes físicos

Objetivo: separar claramente o que foi comprovado em cada combinação de sistema/sessão/backend.

Primeira matriz prevista:

- Linux Mint / X11;
- Ubuntu / X11;
- Wayland somente quando houver backend validado;
- navegador Playwright e desktop físico registrados separadamente.

Critérios de aceite:

- nunca extrapolar PASS de um ambiente para outro;
- STATUS distingue baseline histórica de evidência da versão atual;
- incompatibilidades conhecidas aparecem antes do smoke.

## Ordem proposta

```text
Durable Journal + falha-robo comprovados fisicamente
        ↓
R1 — teste-robo
        ↓
R3 — pacote de evidências
        ↓
R2 — integração no Painel
        ↓
R4 — histórico
        ↓
R5 — expansão da matriz física conforme necessidade
```

Essa ordem pode mudar somente quando uma necessidade real do projeto justificar a mudança. O roadmap não autoriza implementação automática desses itens.
