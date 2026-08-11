# LOCAL VALIDATION

## Objetivo

Reduzir a atualização e a validação do host Linux/X11 a poucos comandos estáveis, sem esconder falhas e sem usar operações Git destrutivas.

## Atualização local

Comando oficial:

```bash
atualizar-robo
```

Contrato:

1. confirma que `origin` aponta para `leon337/project-memory`;
2. recusa continuar se a working tree tiver alterações locais;
3. executa `git fetch origin main`;
4. recusa continuar se a `main` local tiver commits não publicados;
5. muda para `main` somente com árvore limpa;
6. atualiza apenas por fast-forward;
7. cria `.venv` se necessário;
8. sincroniza `.[dev]` no ambiente virtual;
9. sincroniza o Chromium do Playwright;
10. mostra commit instalado e resultado final.

O comando não usa `git reset --hard`, `git clean`, force-push, rebase automático nem descarte implícito de arquivos.

## Validação local

Comando oficial:

```bash
validar-robo
```

Ele verifica:

- repositório esperado;
- working tree limpa;
- branch `main`;
- Python 3.11+ no `.venv`;
- compilação de `src` e `tests`;
- suíte `pytest` completa;
- backend desktop habilitado;
- sessão X11;
- PyAutoGUI, Pillow e PyScreeze;
- `xdotool` e `scrot`;
- Chromium do Playwright.

Resultado operacional:

```text
RESULTADO: PRONTO PARA TESTE FÍSICO
```

ou:

```text
RESULTADO: STOP — CORRIGIR ITENS FAIL ANTES DO TESTE FÍSICO
```

O validador não executa ações físicas no desktop.

## Fault injection físico controlado

Comando local:

```bash
falha-robo listar
falha-robo status
falha-robo armar <checkpoint>
falha-robo limpar
```

Checkpoints disponíveis:

```text
after_prepare
after_in_flight
after_backend
after_executed
before_ack
after_ack
```

Semântica:

- `after_prepare`: journal está `prepared`; backend físico ainda não entrou;
- `after_in_flight`: journal já está `in_flight`; backend ainda não foi chamado, mas o recovery deve tratar o estado como ambíguo/fail-closed para ação não repeat-safe;
- `after_backend`: ação física real retornou, journal ainda está `in_flight`;
- `after_executed`: receipt mínimo já foi persistido como `executed`;
- `before_ack`: Goal Runtime terminou a tentativa e o resultado ainda não foi aceito pela Central;
- `after_ack`: Central já aceitou o resultado terminal.

O mecanismo é **one-shot**. O arquivo de armamento é consumido atomicamente antes do encerramento proposital do processo do Robô. O restart não repete automaticamente o mesmo crash.

A falha controlada não simula mouse, teclado, Playwright ou backend. Ela somente encerra o processo local do Robô em um ponto conhecido; a ação física, o SQLite, o journal, o lease, o reclaim e o restart continuam reais.

## Segurança e privacidade

- fault injection é armado apenas por arquivo local de runtime; não existe endpoint web/Central para armá-lo;
- o mecanismo permanece desarmado por padrão;
- somente o processo local do Robô é encerrado;
- o último evento persiste apenas checkpoint, PID e identificadores técnicos (`task_id`, `action_key`, `action_name`, status);
- texto bruto do target/comando não entra no registro de fault injection;
- `runtime/` continua fora do Git.

## Fluxo humano recomendado

Para uma nova versão já publicada:

```text
atualizar-robo
      ↓
validar-robo
      ↓
PASS automatizado
      ↓
abrir Painel
      ↓
executar um cenário físico por vez
      ↓
analisar PASS/FAIL antes do próximo cenário
```

No smoke do Durable Journal, `falha-robo` é armado somente imediatamente antes do cenário correspondente.
