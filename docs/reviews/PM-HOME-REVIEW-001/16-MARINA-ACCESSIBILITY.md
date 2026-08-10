# PM-HOME-REVIEW-001 — Marina — Acessibilidade

## Entrada recebida
Estrutura visual de Isabela e fluxo UX de Laura.

## Trabalho executado
Revisão de acessibilidade para uso por teclado, leitor de tela, zoom e baixa visão.

## Requisitos obrigatórios
- alvo: WCAG 2.2 AA;
- foco visível em todos os controles;
- ordem de tabulação acompanha a hierarquia visual;
- botões com nomes acessíveis completos, não apenas ícones;
- estados `online/offline`, `executando`, `falhou`, `bloqueado` e `emergência` expressos também por texto;
- atualizações de execução em região de status apropriada (`aria-live`), sem excesso de anúncios;
- erros críticos em região de alerta;
- `prefers-reduced-motion` respeitado;
- zoom de 200% sem perda de função;
- controles compactos não podem reduzir área clicável a ponto de prejudicar toque/coordenação motora;
- contraste suficiente em texto secundário e badges;
- atalhos de teclado documentados e sem conflito com tecnologias assistivas.

## Pontos específicos da V4
1. O painel `Agente agora` não pode ser a única fonte do status; o chat também precisa comunicar resultado.
2. A faixa superior deve ter rótulos textuais permanentes ou acessíveis.
3. Chips de atalhos são secundários e precisam permanecer navegáveis por teclado.
4. A emergência deve ser reconhecível sem depender do vermelho.

## Decisão
`PASS_WITH_CHANGES`.

## Handoff
**Marina → Sofia**

Entrega: critérios WCAG e barreiras de interação.
Próxima ação: definir arquitetura da Home preservando separação de responsabilidades e telemetria real.
Critério de conclusão: componentes e fluxos técnicos que consigam satisfazer os requisitos de experiência sem duplicar o runtime.