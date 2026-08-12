const STATES = {
  executing: {
    phase: 'Executando',
    phaseClass: 'phase-executing',
    noticeClass: 'neutral-notice',
    noticeTitle: 'Publicando branch',
    noticeDescription: 'O Robô está executando a próxima ação autorizada. A conclusão ainda não foi comprovada.',
    progress: 40,
    progressLabel: '2 de 5 comprovadas',
    currentPosition: 'Etapa atual: 3 de 5',
    stepState: 'Executando',
    stepSubtitle: 'Rota selecionada: Git CLI',
    currentClass: 'executing',
    provedCount: 2,
    activeCount: 1,
    activeLabel: 'Em andamento',
    pendingCount: 2,
    summarySentence: 'A etapa 3 está em execução. Apenas 2 etapas contam como progresso comprovado.',
    capability: 'git.branch.publish',
    route: 'Git CLI',
    verificationTitle: 'Executado não significa comprovado',
    verificationDescription: 'A próxima etapa será marcada como concluída somente depois que uma observação independente confirmar o estado esperado.',
    journal: 'in_flight',
    recovery: 'armed'
  },
  verifying: {
    phase: 'Verificando',
    phaseClass: 'phase-verifying',
    noticeClass: 'verify-notice',
    noticeTitle: 'Verificando branch remota',
    noticeDescription: 'A execução técnica terminou. O Robô está lendo o estado remoto por um caminho de observação independente.',
    progress: 40,
    progressLabel: '2 de 5 comprovadas',
    currentPosition: 'Etapa atual: 3 de 5 · verificando',
    stepState: 'Verificando',
    stepSubtitle: 'Execução concluída · aguardando evidência remota',
    currentClass: 'verifying',
    provedCount: 2,
    activeCount: 1,
    activeLabel: 'Em verificação',
    pendingCount: 2,
    summarySentence: 'A etapa 3 foi executada, mas ainda não conta como concluída. A prova independente está em andamento.',
    capability: 'git.branch.publish',
    route: 'Git CLI + leitura remota',
    verificationTitle: 'Aguardando prova independente',
    verificationDescription: 'O receipt de push não basta. O estado remoto precisa confirmar a branch e o commit esperados.',
    journal: 'executed',
    recovery: 'observe-only'
  },
  recovering: {
    phase: 'Recuperando',
    phaseClass: 'phase-recovering',
    noticeClass: 'recovery-notice',
    noticeTitle: 'Recuperando execução interrompida',
    noticeDescription: 'O Robô está verificando o estado atual antes de qualquer nova ação. Nenhum efeito será repetido cegamente.',
    progress: 40,
    progressLabel: '2 de 5 comprovadas',
    currentPosition: 'Etapa atual: 3 de 5 · recovery',
    stepState: 'Recuperando',
    stepSubtitle: 'Estado anterior precisa ser classificado antes de continuar',
    currentClass: 'recovering',
    provedCount: 2,
    activeCount: 1,
    activeLabel: 'Em recovery',
    pendingCount: 2,
    summarySentence: 'A etapa 3 está em recovery. O progresso comprovado permanece em 2 de 5 até existir nova evidência.',
    capability: 'git.branch.publish',
    route: 'Git CLI · rota fixada',
    verificationTitle: 'Recovery antes de qualquer nova emissão',
    verificationDescription: 'O runtime deve classificar o efeito como presente, ausente ou ambíguo. Estado ambíguo falha fechado.',
    journal: 'in_flight',
    recovery: 'classifying'
  },
  'safe-failure': {
    phase: 'Falha segura',
    phaseClass: 'phase-safe-failure',
    noticeClass: 'failure-notice',
    noticeTitle: 'Execução interrompida com segurança',
    noticeDescription: 'Não foi possível confirmar se a ação externa ocorreu. O Robô não repetirá a ação automaticamente.',
    progress: 40,
    progressLabel: '2 de 5 comprovadas',
    currentPosition: 'Etapa 3 de 5 · falha segura',
    stepState: 'Falha segura',
    stepSubtitle: 'Estado ambíguo · replay automático recusado',
    currentClass: 'safe-failure',
    provedCount: 2,
    activeCount: 1,
    activeLabel: 'Falha segura',
    pendingCount: 2,
    summarySentence: 'A etapa 3 terminou em falha segura. O sistema preservou a ambiguidade e não fabricou progresso.',
    capability: 'git.branch.publish',
    route: 'Git CLI · bloqueada',
    verificationTitle: 'Ambiguidade preservada, não mascarada',
    verificationDescription: 'Falhar é o comportamento correto quando o sistema não consegue provar que repetir o efeito é seguro.',
    journal: 'in_flight',
    recovery: 'ambiguous'
  },
  succeeded: {
    phase: 'Comprovado',
    phaseClass: 'phase-succeeded',
    noticeClass: 'success-notice',
    noticeTitle: 'Objetivo comprovado',
    noticeDescription: 'Todos os critérios obrigatórios possuem evidência suficiente. O GoalVerifier pode autorizar conclusão.',
    progress: 100,
    progressLabel: '5 de 5 comprovadas',
    currentPosition: 'Objetivo concluído',
    stepState: 'Comprovado',
    stepSubtitle: 'Branch remota confirmada no estado esperado',
    currentClass: 'succeeded',
    provedCount: 5,
    activeCount: 0,
    activeLabel: 'Em andamento',
    pendingCount: 0,
    summarySentence: 'Todas as 5 etapas estão comprovadas. O percentual representa somente critérios efetivamente fechados.',
    capability: 'goal.verify',
    route: 'Observação independente',
    verificationTitle: 'Estado final comprovado',
    verificationDescription: 'O sucesso representa o objetivo inteiro comprovado, não apenas uma chamada técnica bem-sucedida.',
    journal: 'acknowledged',
    recovery: 'not-required'
  }
};

const stateButtons = [...document.querySelectorAll('.state-demo')];
const phasePill = document.getElementById('phasePill');
const operationNotice = document.getElementById('operationNotice');
const noticeTitle = document.getElementById('noticeTitle');
const noticeDescription = document.getElementById('noticeDescription');
const progressBar = document.getElementById('progressBar');
const progressPercent = document.getElementById('progressPercent');
const progressLabel = document.getElementById('progressLabel');
const currentPositionLabel = document.getElementById('currentPositionLabel');
const currentStepState = document.getElementById('currentStepState');
const currentStepSubtitle = document.getElementById('currentStepSubtitle');
const verificationTitle = document.getElementById('verificationTitle');
const verificationDescription = document.getElementById('verificationDescription');
const provedCount = document.getElementById('provedCount');
const activeCount = document.getElementById('activeCount');
const pendingCount = document.getElementById('pendingCount');
const activeMetricLabel = activeCount?.nextElementSibling;
const summarySentence = document.getElementById('summarySentence');
const drawerCapability = document.getElementById('drawerCapability');
const drawerRoute = document.getElementById('drawerRoute');
const drawerJournal = document.getElementById('drawerJournal');
const drawerRecovery = document.getElementById('drawerRecovery');
const steps = [...document.querySelectorAll('.step')];

function resetStepVisuals(state) {
  steps.forEach((step, index) => {
    const marker = step.querySelector('.step-marker');
    const stepState = step.querySelector('.step-state');
    const stepNumber = index + 1;

    step.className = 'step';

    if (state.currentClass === 'succeeded') {
      step.classList.add('completed');
      marker.textContent = '✓';
      stepState.textContent = 'Comprovado';
      return;
    }

    if (stepNumber <= 2) {
      step.classList.add('completed');
      marker.textContent = '✓';
      stepState.textContent = 'Comprovado';
      return;
    }

    if (stepNumber === 3) {
      step.classList.add('current', state.currentClass);
      marker.textContent = '3';
      stepState.textContent = state.stepState;
      return;
    }

    step.classList.add('pending');
    marker.textContent = String(stepNumber);
    stepState.textContent = 'Pendente';
  });
}

function applyState(key) {
  const state = STATES[key];
  if (!state) return;

  phasePill.className = `phase-pill ${state.phaseClass}`;
  phasePill.textContent = state.phase;

  operationNotice.className = `operation-notice ${state.noticeClass}`;
  noticeTitle.textContent = state.noticeTitle;
  noticeDescription.textContent = state.noticeDescription;

  progressBar.style.width = `${state.progress}%`;
  progressPercent.textContent = `${state.progress}%`;
  progressLabel.textContent = state.progressLabel;
  currentPositionLabel.textContent = state.currentPosition;

  currentStepState.textContent = state.stepState;
  currentStepSubtitle.textContent = state.stepSubtitle;
  resetStepVisuals(state);

  provedCount.textContent = String(state.provedCount);
  activeCount.textContent = String(state.activeCount);
  pendingCount.textContent = String(state.pendingCount);
  if (activeMetricLabel) activeMetricLabel.textContent = state.activeLabel;
  summarySentence.textContent = state.summarySentence;

  verificationTitle.textContent = state.verificationTitle;
  verificationDescription.textContent = state.verificationDescription;

  drawerCapability.textContent = state.capability;
  drawerRoute.textContent = state.route.toLowerCase().replaceAll(' ', '-');
  drawerJournal.textContent = state.journal;
  drawerRecovery.textContent = state.recovery;

  stateButtons.forEach(button => {
    const selected = button.dataset.demoState === key;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
}

stateButtons.forEach(button => {
  button.addEventListener('click', () => applyState(button.dataset.demoState));
});

document.querySelectorAll('.step-main').forEach(button => {
  button.addEventListener('click', () => {
    const step = button.closest('.step');
    const open = step.classList.toggle('open');
    button.setAttribute('aria-expanded', String(open));
  });
});

document.querySelectorAll('.nav-item').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    button.classList.add('active');
  });
});

const drawer = document.getElementById('technicalDrawer');
const drawerBackdrop = document.getElementById('drawerBackdrop');
const openDrawerButton = document.getElementById('openTechnicalDetails');
const closeDrawerButton = document.getElementById('closeTechnicalDetails');
let lastFocusedElement = null;

function openDrawer() {
  lastFocusedElement = document.activeElement;
  drawer.classList.add('open');
  drawer.setAttribute('aria-hidden', 'false');
  drawerBackdrop.hidden = false;
  closeDrawerButton.focus();
}

function closeDrawer() {
  drawer.classList.remove('open');
  drawer.setAttribute('aria-hidden', 'true');
  drawerBackdrop.hidden = true;
  if (lastFocusedElement instanceof HTMLElement) lastFocusedElement.focus();
}

openDrawerButton.addEventListener('click', openDrawer);
closeDrawerButton.addEventListener('click', closeDrawer);
drawerBackdrop.addEventListener('click', closeDrawer);

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && drawer.classList.contains('open')) closeDrawer();
});

applyState('executing');
