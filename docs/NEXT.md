# NEXT

## 1. Limpar o working tree local com preservação e sincronizar o host

O host Linux ainda contém arquivos pessoais/auxiliares não rastreados pelo Git, e `atualizar-robo` para corretamente enquanto a árvore estiver suja. A `main` agora contém `context_anchor.local_archive` e o comando `empacotar-locais`, mas o host ainda precisa receber essa versão.

Para romper esse bootstrap sem descartar nada, executar a versão atual de `src/context_anchor/local_archive.py` diretamente a partir da `main`: ela deve selecionar somente arquivos retornados por `git ls-files --others --exclude-standard`, criar um ZIP fora do repositório na Área de Trabalho, verificar integridade e SHA-256 e somente depois remover os originais arquivados. Alteração em arquivo rastreado, symlink, destino dentro do repositório ou falha de verificação deve resultar em STOP sem remoção dos originais.

Depois de confirmar `RESULTADO: ARQUIVOS LOCAIS PRESERVADOS E REPOSITÓRIO LIMPO`, executar `atualizar-robo` e em seguida `validar-robo`. Não iniciar o teste visual enquanto a atualização ou a validação local não estiverem verdes.

## 2. Auditar o protótipo visual repo-local e decidir a RC 3.5

O protótipo está em `prototypes/pm-universal-operator-ui/` usando somente HTML, CSS e JavaScript versionados no Git. Depois da sincronização e validação local, abrir o protótipo e revisar os estados `executing`, `verifying`, `recovering`, falha segura e `succeeded`, a camada de detalhes técnicos, hierarquia visual, responsividade, acessibilidade e clareza.

A mesma revisão deve aprovar, modificar ou rejeitar as conclusões da RC 3.5 antes de alterar `ARCHITECTURE.md` ou `DECISIONS.md`. Os dados do protótipo continuam simulados; logs não podem ser fonte de verdade visual e nenhum estado sem fonte estruturada no runtime/Central pode ser promovido para a Home operacional.

## 3. Realizar a quarta rodada e converter o desenho aprovado em contrato executável

Somente após a aprovação da RC 3.5 e da arquitetura de informação materializada no protótipo local, realizar a quarta rodada para congelar os contratos do primeiro slice Git/GitHub sandbox e transformar o resultado em issue/missão implementável, com critérios de aceitação, capacidades, sequência de entrega, testes e evidências exigidas.

Toda nova capacidade deve preservar Policy Layer, lease/heartbeat, Durable Journal, FAILSAFE, Emergency Stop, percepção independente, EvidenceRecord e GoalVerifier como única autoridade de conclusão. A identidade durável de efeitos externos não pode permitir replay cego entre rotas ou retries/reclaims.
