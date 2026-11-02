const form = document.querySelector('#job-form');
const libraryCard = document.querySelector('#library-card');
const speakerRegistryCard = document.querySelector('#speaker-registry-card');
const analysisCard = document.querySelector('#analysis-card');
const analysisItemSelect = document.querySelector('#analysis-item-select');
const analysisDesktopContent = document.querySelector('#analysis-desktop-content');
const analysisMobileContent = document.querySelector('#analysis-mobile-content');
const speakerRegistryBody = document.querySelector('#speaker-registry-body');
const speakerRegistryList = document.querySelector('#speaker-registry-list');
const speakerRegistrySaveButton = document.querySelector('#save-speakers-button');
const speakerRegistrySaveState = document.querySelector('#registry-save-state');
const sourcePath = document.querySelector('#source-path');
const inputFile = document.querySelector('#input-file');
const browsePathButton = document.querySelector('#browse-path-button');
const pathDetail = document.querySelector('#path-detail');
const pathError = document.querySelector('#path-error');
const fileDropZone = document.querySelector('#file-drop-zone');
const sourcePreview = document.querySelector('#source-preview');
const sourceThumbnail = document.querySelector('#source-thumbnail');
const sourcePreviewMessage = document.querySelector('#source-preview-message');
const formError = document.querySelector('#form-error');
const startButton = document.querySelector('#start-button');
const progressCard = document.querySelector('#progress-card');
const resultCard = document.querySelector('#result-card');
const cancelButton = document.querySelector('#cancel-button');
const saveButton = document.querySelector('#save-button');
const newButton = document.querySelector('#new-button');
const resultAnalysisButton = document.querySelector('#result-analysis-button');
const resultContextButtons = [...document.querySelectorAll('[data-result-destination]')];
const meetingMinutesView = document.querySelector('#meeting-minutes-view');
const meetingCopyJsonButton = document.querySelector('#meeting-copy-json');
const meetingObsidianSaveButton = document.querySelector('#meeting-obsidian-save');
const meetingObsidianOpenLink = document.querySelector('#meeting-obsidian-open');
const meetingObsidianStatus = document.querySelector('#meeting-obsidian-status');
const deleteRecordButton = document.querySelector('#delete-record-button');
const boostQuietSpeech = document.querySelector('#boost-quiet-speech');
const triplePass = document.querySelector('#triple-pass');
const vadOnset = document.querySelector('#vad-onset');
const vadOffset = document.querySelector('#vad-offset');
const emotionAnalysis = document.querySelector('#emotion-analysis');
const emotionModel = document.querySelector('#emotion-model');
const aiProvider = document.querySelector('#ai-provider');
const modelName = document.querySelector('#model-name');
const transcriptionBackend = document.querySelector('#transcription-backend');
const languageSelect = document.querySelector('[name="language"]');
const audioPreprocess = document.querySelector('[name="audio_preprocess"]');
const minSpeakersInput = document.querySelector('[name="min_speakers"]');
const maxSpeakersInput = document.querySelector('[name="max_speakers"]');
const speakerCountFixButton = document.querySelector('#speaker-count-fix');
const fixedSpeakerCountInput = document.querySelector('#fixed-speaker-count');
const fixedSpeakerCountField = document.querySelector('#fixed-speaker-count-field');
const minSpeakersField = document.querySelector('#min-speakers-field');
const maxSpeakersField = document.querySelector('#max-speakers-field');
const conversationModeInputs = [...document.querySelectorAll('input[name="conversation_mode"]')];
const conversationModeHint = document.querySelector('#conversation-mode-hint');
const conversationModeResetButton = document.querySelector('#conversation-mode-reset');
const writeSrt = document.querySelector('[name="write_srt"]');
const burnSubtitledVideo = document.querySelector('[name="burn_subtitled_video"]');
const customVocabulary = document.querySelector('#custom-vocabulary');
const customVocabularyStatus = document.querySelector('#custom-vocabulary-status');
const qwenBackendNote = document.querySelector('#qwen-backend-note');
const qwenVocabularyNote = document.querySelector('#qwen-vocabulary-note');
const setupReadyState = document.querySelector('#setup-ready-state');
const setupSummary = document.querySelector('#setup-summary');
const createView = document.querySelector('#create-view');
const flowStepItems = [...document.querySelectorAll('[data-flow-step]')];
const flowSections = [...document.querySelectorAll('[data-flow-section]')];
const settingsPanels = [...document.querySelectorAll('[data-settings-panel]')];
const mobileStepBack = document.querySelector('#mobile-step-back');
const mobileStepNext = document.querySelector('#mobile-step-next');
const mobileNavStep = document.querySelector('#mobile-nav-step');
const mobileNavLabel = document.querySelector('#mobile-nav-label');
const jobChip = document.querySelector('#job-chip');
const jobChipLabel = document.querySelector('#job-chip-label');
const itemTabButtons = [...document.querySelectorAll('[data-item-tab]')];
const itemPanels = [...document.querySelectorAll('[data-item-panel]')];
const mobileWizardMedia = window.matchMedia('(max-width: 959px)');
const cleanTranscript = document.querySelector('#clean-transcript');
const detectNames = document.querySelector('#detect-names');
const createOutline = document.querySelector('#create-outline');
const finishInObsidian = document.querySelector('#finish-in-obsidian');
const jevCompare = document.querySelector('#jev-compare');
const transcriptFinishingModeInputs = [...document.querySelectorAll('input[name="transcript_finishing_mode"]')];
const finishingModeHint = document.querySelector('#finishing-mode-hint');
const jevConfigStatus = document.querySelector('#jev-config-status');
const speakerIdentityProvider = document.querySelector('#speaker-identity-provider');
const rerunSpeakerIdentificationButton = document.querySelector('#rerun-speaker-identification');
const speakerIdentityStatus = document.querySelector('#speaker-identity-status');
const showLibraryButton = document.querySelector('#show-library-button');
const showAnalysisButton = document.querySelector('#show-analysis-button');
const processedDataHub = document.querySelector('#processed-data-hub');
const showLibraryListButton = document.querySelector('#show-library-list-button');
const showLibraryAnalysisButton = document.querySelector('#show-library-analysis-button');
const showNewButton = document.querySelector('#show-new-button');
const showSpeakersButton = document.querySelector('#show-speakers-button');
const libraryGroupDialog = document.querySelector('#library-group-dialog');
const libraryGroupList = document.querySelector('#library-group-list');
const libraryGroupMessage = document.querySelector('#library-group-message');
const segmentEditor = document.querySelector('#segment-editor');
const speakerEditor = document.querySelector('#speaker-editor');
const mediaReview = document.querySelector('#media-review');
const mediaPlayerHost = document.querySelector('#media-player-host');
const bootSplash = document.querySelector('#boot-splash');
const aiOptionInputs = [cleanTranscript, detectNames, createOutline].filter(Boolean);
const aiModelDialog = document.querySelector('#ai-model-dialog');
const aiModelForm = document.querySelector('#ai-model-form');
const aiModelProviderLabel = document.querySelector('#ai-model-provider-label');
const aiModelCurrent = document.querySelector('#ai-model-current');
const aiModelSearch = document.querySelector('#ai-model-search');
const aiModelSelect = document.querySelector('#ai-model-select');
const aiModelDescription = document.querySelector('#ai-model-description');
const aiModelError = document.querySelector('#ai-model-error');
const saveAiModelButton = document.querySelector('#save-ai-model-button');

let tokenConfigSnapshot = {};
let configLoadState = 'loading';
let lastMachineProfile = null;
const manuallySelectedMachineFields = new Set();
const deletingLibraryItems = new Set();
let pendingSpeakerImport = null;
let deletedSegmentUndo = [];
let currentJobBaseline = null;
let speakerRegistryBaseline = [];
let resultSaveConflict = false;
let speakerSaveConflict = false;
let aiProviderManuallySelected = false;
let aiModelCatalog = [];
let activeAiModelProvider = '';

let currentJobId = null;
let currentJob = null;
// The job being polled is separate from the record on screen, so a running
// job never redirects a save of another record.
let activeJobId = null;
let lastProgressJob = null;
let completedJob = null;
let activeItemTab = 'transcript';
let renderedItemId = null;
let currentRouteHash = '';
let pollTimer = null;
let systemActivityTimer = null;
let systemActivityController = null;
let pollFailureCount = 0;
let jobFlowGeneration = 0;
let mediaPlayer = null;
let selectedSegmentId = null;
let playbackStopAt = null;
let libraryTimer = null;
let thumbnailTimer = null;
let thumbnailRequestId = 0;
let sourceThumbnailController = null;
let sourceThumbnailObjectUrl = null;
let jobRunning = false;
let currentJobDirty = false;
let currentJobMutationGeneration = 0;
let meetingObsidianStatusGeneration = 0;
let currentMobileStep = 1;
let customVocabularyTouched = false;
let customVocabularyMutationGeneration = 0;
let customVocabularySaveTimer = null;
let speakerRegistry = [];
let speakerRegistryDeletedIds = new Set();
let speakerRegistryLoaded = false;
let speakerRegistryRevision = 0;
let speakerRegistryDirty = false;
let speakerRegistryMutationGeneration = 0;
let speakerRegistrySaveInProgress = false;
let speakerSurveyAnalysisTimer = null;
const speakerSurveyAnalysisState = {
  primaryQuestion: '',
  secondaryQuestion: '',
  answerFilter: '',
  includeInactive: false
};
let libraryRequestController = null;
let libraryRequestSequence = 0;
let libraryPageOffset = 0;
let libraryPageFilter = '';
let libraryGroups = [];
let trainingStatusLoaded = false;
let analysisCatalogLoaded = false;
let analysisCatalog = [];
let analysisRequestController = null;
let analysisRequestSequence = 0;
let analysisSaveInProgress = false;
let analysisSaveOwner = null;
const segmentClassificationRequests = new Map();
let analysisNavigationGeneration = 0;
function captureAnalysisContext() {
  return {itemId: analysisState.itemId, data: analysisState.data, navigation: analysisNavigationGeneration,
    mutation: analysisMutationGeneration, sourceRevision: analysisState.data?.item?.revision_count,
    analysisRevision: analysisState.data?.item?.analysis_revision};
}
function isAnalysisContextCurrent(context) {
  return context.itemId === analysisState.itemId && context.data === analysisState.data
    && context.navigation === analysisNavigationGeneration && context.mutation === analysisMutationGeneration
    && context.sourceRevision === analysisState.data?.item?.revision_count
    && context.analysisRevision === analysisState.data?.item?.analysis_revision;
}
function segmentClassificationBusy() { return segmentClassificationRequests.has(analysisState.itemId); }

let analysisMutationGeneration = 0;
let analysisInitialSectionApplied = false;
let analysisNavigationFrame = 0;
let analysisTermRunRequested = false;
const analysisState = {
  itemId: '',
  mode: 'automatic',
  data: null,
  config: {},
  annotations: {},
  dirty: false,
  segmentQuery: '',
  annotatedOnly: false,
  automaticScope: 'overall',
  automaticPage: 'overview',
  speakerSort: 'speaking_desc',
  speakerAttributeFilter: '',
  selectedSpeaker: '',
  methods: null
};
const dialogueActLabels = {
  question: '質問・問題提起', answer: '回答・説明', proposal: '提案・選択肢',
  request: '依頼・要望', confirmation: '確認', agreement: '同意・賛同',
  reservation: '留保・条件付き', objection: '反対・異論',
  self_correction: '自己訂正・言い直し', backchannel: '相づち・短い応答',
  information: '情報・経験の共有', other: 'その他・保留'
};
const activeJobStorageKey = 'gurumoji.activeJobId';
const pendingSubmissionStorageKey = 'gurumoji.pendingSubmission';
const pollBaseDelayMs = 1200;
const pollMaxDelayMs = 30000;
const systemActivityDelayMs = 1200;
const submitRecoveryMaxAttempts = 6;
let browserFilePickerOnly = browsePathButton
  ? browsePathButton.dataset.pickerMode === 'browser'
  : false;

const speakerRoleLabels = {
  participant: '参加者',
  moderator: '司会・モデレーター',
  facilitator: '進行・ファシリテーター',
  assistant_moderator: '副司会',
  observer: '観察者',
  note_taker: '記録者・書記',
  interviewer: 'インタビュアー',
  chair: '議長',
  presenter: '発表者',
  decision_maker: '意思決定者',
  attendee: '出席者',
  guest: 'ゲスト',
  other: 'その他'
};
const consentLabels = {
  unknown: '未確認',
  pending: '確認中',
  granted: '同意済み',
  declined: '非同意',
  not_required: '不要'
};
const attendanceLabels = {
  unknown: '未確認',
  planned: '予定',
  attended: '参加',
  absent: '欠席',
  left_early: '途中退出',
  remote: 'オンライン'
};
const speakerThemeColors = [
  '#E86A5A', '#2F80ED', '#27AE60', '#9B51E0', '#F2994A', '#00A6A6',
  '#EB5FA7', '#7A6FBE', '#6C8B3C', '#C47F17', '#3E8ED0', '#B85C5C',
  '#D1495B', '#00798C', '#6A4C93', '#8F5B34', '#B33C86', '#4D9078',
  '#E4572E', '#577590'
];

const mobileStepContent = {
  1: {label: 'ファイル', next: '設定へ'},
  2: {label: '設定', next: '確認へ'},
  3: {label: '開始', next: '開始'}
};

const conversationModePresets = {
  meeting: {
    label: '会議モード',
    minSpeakers: 2,
    maxSpeakers: 10,
    audioPreprocess: 'standard',
    boostQuietSpeech: true,
    triplePass: false,
    vadOnset: '0.35',
    vadOffset: '0.25',
    hint: '会議向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。'
  },
  group_interview: {
    label: 'グループインタビューモード',
    minSpeakers: 3,
    maxSpeakers: 12,
    audioPreprocess: 'standard',
    boostQuietSpeech: true,
    triplePass: false,
    vadOnset: '0.30',
    vadOffset: '0.22',
    hint: 'グループインタビュー向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。'
  },
  chat: {
    label: '雑談モード',
    minSpeakers: 2,
    maxSpeakers: 6,
    audioPreprocess: 'light',
    boostQuietSpeech: true,
    triplePass: false,
    vadOnset: '0.42',
    vadOffset: '0.30',
    hint: '雑談向けの設定を適用中。話者数や前処理は「認識・話者分離」で変更できます。'
  }
};

loadConfig();
loadCustomVocabulary();
loadSpeakerRegistry();
restoreActiveJob();
startBootSequence();

function startBootSequence() {
  if (!bootSplash) {
    document.body.classList.remove('booting');
    return;
  }
  // The splash is an intro, not a real check: show it once per browser session
  // and keep it short, so reloads go straight to the workspace (UX-08).
  let seen = false;
  try {
    seen = window.sessionStorage.getItem('gurumoji.bootSplashSeen') === '1';
    window.sessionStorage.setItem('gurumoji.bootSplashSeen', '1');
  } catch (error) {
    seen = false;
  }
  if (seen) {
    bootSplash.hidden = true;
    bootSplash.setAttribute('aria-hidden', 'true');
    document.body.classList.add('boot-skipped');
    document.body.classList.remove('booting');
    return;
  }
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  window.setTimeout(() => {
    bootSplash.classList.add('show-main');
    window.setTimeout(() => {
      bootSplash.classList.add('is-leaving');
      document.body.classList.remove('booting');
      window.setTimeout(() => {
        bootSplash.hidden = true;
        bootSplash.setAttribute('aria-hidden', 'true');
      }, reducedMotion ? 50 : 400);
    }, reducedMotion ? 150 : 650);
  }, reducedMotion ? 200 : 1200);
}

function setAlert(element, message, error = false) {
  if (!element) return;
  element.setAttribute('role', error ? 'alert' : 'status');
  element.setAttribute('aria-live', error ? 'assertive' : 'polite');
  element.setAttribute('aria-atomic', 'true');
  element.textContent = message || '';
  element.hidden = !message;
  element.classList.toggle('error', error);
}

function listen(element, eventName, handler) {
  if (element) element.addEventListener(eventName, handler);
}

function apiFetch(input, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  if (!['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    return window.fetch(input, options);
  }
  const headers = new Headers(options.headers || {});
  headers.set('X-Gurumoji-Request', '1');
  return window.fetch(input, {...options, headers});
}

function deepCopy(value) {
  return JSON.parse(JSON.stringify(value));
}

function storedActiveJobId() {
  try {
    return String(window.sessionStorage.getItem(activeJobStorageKey) || '').trim();
  } catch (_) {
    return '';
  }
}

function storeActiveJobId(jobId) {
  try {
    if (jobId) window.sessionStorage.setItem(activeJobStorageKey, String(jobId));
    else window.sessionStorage.removeItem(activeJobStorageKey);
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function storedPendingSubmissionId() {
  try {
    const raw = window.sessionStorage.getItem(pendingSubmissionStorageKey);
    if (!raw) return '';
    const pending = JSON.parse(raw);
    const submissionId = String(pending && pending.id || '').trim();
    const createdAt = Number(pending && pending.createdAt);
    if (!/^[0-9a-f]{32}$/.test(submissionId)
        || !Number.isFinite(createdAt)) {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
      return '';
    }
    return submissionId;
  } catch (_) {
    try { window.sessionStorage.removeItem(pendingSubmissionStorageKey); } catch (_) {}
    return '';
  }
}

function storePendingSubmissionId(submissionId, retryAllowed = false) {
  try {
    if (submissionId) {
      window.sessionStorage.setItem(pendingSubmissionStorageKey, JSON.stringify({
        id: String(submissionId),
        createdAt: Date.now(),
        retryAllowed: Boolean(retryAllowed)
      }));
    } else {
      window.sessionStorage.removeItem(pendingSubmissionStorageKey);
    }
  } catch (_) {
    // Storage can be unavailable in hardened or private browser contexts.
  }
}

function pendingSubmissionRetryAllowed(submissionId) {
  try {
    const pending = JSON.parse(window.sessionStorage.getItem(pendingSubmissionStorageKey) || '{}');
    return pending.id === submissionId && pending.retryAllowed === true;
  } catch (_) {
    return false;
  }
}

function markPendingSubmissionRetryable(submissionId) {
  storePendingSubmissionId(submissionId, true);
}

function createSubmissionId() {
  if (window.crypto && typeof window.crypto.randomUUID === 'function') {
    return window.crypto.randomUUID().replaceAll('-', '');
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}

function setCurrentJobDirty(dirty = true, trackMutation = true) {
  currentJobDirty = Boolean(dirty);
  if (currentJobDirty && trackMutation) currentJobMutationGeneration += 1;
  if (resultCard) resultCard.classList.toggle('has-unsaved', currentJobDirty);
  if (saveButton) saveButton.classList.toggle('unsaved', currentJobDirty);
}

async function readJsonResponse(response) {
  const body = await response.text();
  if (!body) return {};
  try {
    return JSON.parse(body);
  } catch (error) {
    const status = `${response.status} ${response.statusText}`.trim();
    const looksLikeHtml = body.trimStart().startsWith('<')
      || (response.headers.get('content-type') || '').includes('text/html');
    if (looksLikeHtml) {
      throw new Error(
        `サーバーからHTMLエラーが返されました（${status}）。アプリを再起動してページを再読み込みしてください。`
      );
    }
    throw new Error(`サーバー応答を読み取れませんでした（${status}）。`);
  }
}

function vocabularyTermsFromInput(value = customVocabulary && customVocabulary.value) {
  return String(value || '')
    .split(/\r?\n/)
    .map(term => term.trim())
    .filter(Boolean);
}

function setCustomVocabularyStatus(message, error = false) {
  if (!customVocabularyStatus) return;
  customVocabularyStatus.textContent = message;
  customVocabularyStatus.classList.toggle('error', error);
}

function customVocabularyCountLabel(terms) {
  const count = Array.isArray(terms) ? terms.length : 0;
  return count ? `${count}語を登録` : '未登録';
}

async function loadCustomVocabulary() {
  if (!customVocabulary) return;
  try {
    const response = await apiFetch('/api/custom-vocabulary', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を読み込めませんでした。');
    const terms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    if (!customVocabularyTouched) customVocabulary.value = terms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(
      customVocabularyTouched ? vocabularyTermsFromInput() : terms
    ));
    updateCreateSummary();
  } catch (error) {
    setCustomVocabularyStatus(error.message || '単語登録を読み込めませんでした。', true);
  }
}

async function saveCustomVocabulary(saveGeneration) {
  if (!customVocabulary) return;
  const sourceText = customVocabulary.value;
  const terms = vocabularyTermsFromInput(sourceText);
  setCustomVocabularyStatus('保存中…');
  try {
    const response = await apiFetch('/api/custom-vocabulary', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({terms})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '単語登録を保存できませんでした。');
    if (saveGeneration !== customVocabularyMutationGeneration) return;
    const savedTerms = Array.isArray(data.terms) ? data.terms.map(term => String(term).trim()).filter(Boolean) : [];
    customVocabulary.value = savedTerms.join('\n');
    setCustomVocabularyStatus(customVocabularyCountLabel(savedTerms));
    updateCreateSummary();
  } catch (error) {
    if (saveGeneration === customVocabularyMutationGeneration) {
      setCustomVocabularyStatus(error.message || '単語登録を保存できませんでした。', true);
    }
  }
}

function scheduleCustomVocabularySave({immediate = false} = {}) {
  if (!customVocabulary) return;
  if (customVocabularySaveTimer !== null) window.clearTimeout(customVocabularySaveTimer);
  const saveGeneration = customVocabularyMutationGeneration;
  setCustomVocabularyStatus('保存待ち…');
  const save = () => {
    customVocabularySaveTimer = null;
    saveCustomVocabulary(saveGeneration);
  };
  if (immediate) save();
  else customVocabularySaveTimer = window.setTimeout(save, 450);
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function formatTime(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h
    ? `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
    : `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function formatDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value || '' : new Intl.DateTimeFormat('ja-JP', {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  }).format(date);
}

function selectedOptionText(select) {
  return select && select.selectedOptions && select.selectedOptions[0]
    ? select.selectedOptions[0].textContent.trim()
    : '';
}

function hasSelectedSource() {
  return Boolean(
    (sourcePath && sourcePath.value.trim())
    || (inputFile && inputFile.files && inputFile.files.length)
  );
}

function isMobileWizard() {
  return mobileWizardMedia.matches;
}

function updateBrowseButtonLabel() {
  if (!browsePathButton || browsePathButton.disabled) return;
  browsePathButton.textContent = isMobileWizard()
    ? '端末から選択'
    : (browserFilePickerOnly ? '端末からアップロード' : 'ファイルを選択');
}

const reducedMotionMedia = window.matchMedia('(prefers-reduced-motion: reduce)');
function scrollBehavior() {
  return reducedMotionMedia.matches ? 'auto' : 'smooth';
}

// One stepper for every width (UX-05): on a desktop it reports progress and
// scrolls to the section; on a phone it is the wizard's page indicator.
function renderFlowSteps() {
  const hasSource = hasSelectedSource();
  const mobile = isMobileWizard();
  flowStepItems.forEach(item => {
    const step = Number(item.dataset.flowStep);
    item.classList.remove('active', 'complete', 'ready');
    if (mobile) {
      if (step === currentMobileStep) item.classList.add('active');
      else if (step < currentMobileStep) item.classList.add('complete');
      else if (step === 3 && hasSource) item.classList.add('ready');
    } else if (step === 1) {
      item.classList.add(hasSource ? 'complete' : 'active');
    } else if (step === 2) {
      if (hasSource) item.classList.add('active');
    } else if (hasSource) {
      item.classList.add('ready');
    }
    const button = item.querySelector('[data-flow-jump]');
    if (button) button.setAttribute('aria-current', item.classList.contains('active') ? 'step' : 'false');
  });
}

function renderMobileWizard() {
  if (!form) return;
  const mobile = isMobileWizard();
  form.classList.toggle('mobile-wizard-ready', mobile);
  [1, 2, 3].forEach(step => form.classList.toggle(`mobile-step-${step}`, step === currentMobileStep));
  flowSections.forEach(section => {
    const active = Number(section.dataset.flowSection) === currentMobileStep;
    section.classList.toggle('mobile-active', active);
    if (mobile) section.toggleAttribute('inert', !active);
    else section.removeAttribute('inert');
  });
  const content = mobileStepContent[currentMobileStep] || mobileStepContent[1];
  if (mobileNavStep) mobileNavStep.textContent = `${currentMobileStep} / 3`;
  if (mobileNavLabel) mobileNavLabel.textContent = content.label;
  if (mobileStepBack) mobileStepBack.disabled = jobRunning || currentMobileStep === 1;
  if (mobileStepNext) {
    mobileStepNext.disabled = jobRunning || currentMobileStep >= 3 || (currentMobileStep === 1 && !hasSelectedSource());
    mobileStepNext.textContent = content.next;
  }
  renderFlowSteps();
}

function validateMobileStep(step) {
  if (step === 1 && !hasSelectedSource()) {
    setAlert(pathError, '先に音声・動画ファイルを選択してください。', true);
    if (fileDropZone) fileDropZone.focus();
    return false;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === step);
  if (!section) return true;
  const invalid = [...section.querySelectorAll('input, select, textarea')].find(input => !input.checkValidity());
  if (invalid) {
    setAlert(formError, '入力内容を確認してください。', true);
    const panel = invalid.closest('[data-settings-panel]');
    if (panel) panel.open = true;
    invalid.reportValidity();
    invalid.focus();
    return false;
  }
  return true;
}

function setMobileStep(nextStep, {focusHeading = true, validateCurrent = false} = {}) {
  const target = Math.max(1, Math.min(3, Number(nextStep) || 1));
  if (validateCurrent && target > currentMobileStep && !validateMobileStep(currentMobileStep)) return false;
  currentMobileStep = target;
  setAlert(formError, '');
  renderMobileWizard();
  if (focusHeading && isMobileWizard()) {
    const steps = document.querySelector('#flow-steps');
    if (steps) steps.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
    const heading = section ? section.querySelector('h2') : null;
    if (heading) {
      heading.setAttribute('tabindex', '-1');
      window.setTimeout(() => heading.focus({preventScroll: true}), 220);
    }
  }
  return true;
}

function jumpToFlowStep(step) {
  const target = Math.max(1, Math.min(3, Number(step) || 1));
  if (isMobileWizard()) {
    setMobileStep(target, {validateCurrent: target > currentMobileStep});
    return;
  }
  const section = flowSections.find(item => Number(item.dataset.flowSection) === target);
  if (section) section.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
}

// Detailed settings stay closed until asked for; "変更" opens exactly one panel.
function openSettingsPanel(name, {focus = true} = {}) {
  const panel = settingsPanels.find(item => item.dataset.settingsPanel === name);
  if (!panel) return;
  if (isMobileWizard() && currentMobileStep !== 2) setMobileStep(2, {focusHeading: false});
  panel.open = true;
  window.requestAnimationFrame(() => {
    panel.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
    if (!focus) return;
    const control = panel.querySelector('input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled)');
    if (control) window.setTimeout(() => control.focus({preventScroll: true}), 260);
  });
}

function selectedConversationMode() {
  const selected = conversationModeInputs.find(input => input.checked);
  return selected && conversationModePresets[selected.value]
    ? selected.value
    : 'meeting';
}

// Settings a conversation mode writes. A value the user changed by hand is kept
// when the mode changes, so a mode switch never silently discards tuning (UX-14).
const conversationModeFields = [
  {input: minSpeakersInput, key: 'minSpeakers', label: '最少話者数', property: 'value'},
  {input: maxSpeakersInput, key: 'maxSpeakers', label: '最多話者数', property: 'value'},
  {input: audioPreprocess, key: 'audioPreprocess', label: '音声前処理', property: 'value'},
  {input: boostQuietSpeech, key: 'boostQuietSpeech', label: '小さい声を拾いやすくする', property: 'checked'},
  {input: triplePass, key: 'triplePass', label: '詳細処理', property: 'checked'},
  {input: vadOnset, key: 'vadOnset', label: 'VAD onset', property: 'value'},
  {input: vadOffset, key: 'vadOffset', label: 'VAD offset', property: 'value'},
].filter(field => field.input);
const manuallyEditedModeFields = new Set();
let speakerRangeBeforeFix = null;

function isSpeakerCountFixed() {
  return speakerCountFixButton?.getAttribute('aria-pressed') === 'true';
}

function syncFixedSpeakerCount() {
  if (!isSpeakerCountFixed()) return;
  minSpeakersInput.value = fixedSpeakerCountInput.value;
  maxSpeakersInput.value = fixedSpeakerCountInput.value;
  updateCreateSummary();
}

function setSpeakerCountFixed(fixed, {restoreRange = true} = {}) {
  if (fixed) {
    speakerRangeBeforeFix = {
      min: minSpeakersInput.value,
      max: maxSpeakersInput.value,
      editedMin: manuallyEditedModeFields.has('minSpeakers'),
      editedMax: manuallyEditedModeFields.has('maxSpeakers')
    };
    if (minSpeakersInput.value && minSpeakersInput.value === maxSpeakersInput.value) {
      fixedSpeakerCountInput.value = minSpeakersInput.value;
    }
    manuallyEditedModeFields.add('minSpeakers');
    manuallyEditedModeFields.add('maxSpeakers');
  } else if (speakerRangeBeforeFix && restoreRange) {
    minSpeakersInput.value = speakerRangeBeforeFix.min;
    maxSpeakersInput.value = speakerRangeBeforeFix.max;
    if (!speakerRangeBeforeFix.editedMin) manuallyEditedModeFields.delete('minSpeakers');
    if (!speakerRangeBeforeFix.editedMax) manuallyEditedModeFields.delete('maxSpeakers');
  }
  speakerCountFixButton.setAttribute('aria-pressed', String(fixed));
  speakerCountFixButton.textContent = fixed ? '人数の固定を解除する' : '話者数を固定する';
  fixedSpeakerCountField.hidden = !fixed;
  fixedSpeakerCountInput.disabled = !fixed;
  minSpeakersField.hidden = fixed;
  maxSpeakersField.hidden = fixed;
  if (fixed) {
    syncFixedSpeakerCount();
    fixedSpeakerCountInput.focus();
  } else {
    speakerRangeBeforeFix = null;
    applyConversationMode();
  }
}

function applyConversationMode(mode = selectedConversationMode()) {
  const preset = conversationModePresets[mode] || conversationModePresets.meeting;
  if (createView) createView.dataset.conversationMode = conversationModePresets[mode] ? mode : 'meeting';
  const keptLabels = [];
  conversationModeFields.forEach(field => {
    const presetValue = field.property === 'checked' ? preset[field.key] : String(preset[field.key]);
    if (!manuallyEditedModeFields.has(field.key)) {
      field.input[field.property] = presetValue;
    } else if (field.input[field.property] !== presetValue) {
      keptLabels.push(field.label);
    }
  });
  if (conversationModeHint) {
    conversationModeHint.textContent = keptLabels.length
      ? `${preset.hint} 手動で変更した「${keptLabels.join('」「')}」は変更せずに残しています。`
      : preset.hint;
  }
  if (conversationModeResetButton) conversationModeResetButton.hidden = !keptLabels.length;

  // A mode adjusts local, deterministic recognition settings only. External AI
  // remains an explicit choice in the AI finishing section.
  syncQuietFields();
  updateCreateSummary();
}

function syncTranscriptionBackend() {
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron';
  if (qwenSelected && isSpeakerCountFixed()) setSpeakerCountFixed(false);
  if (modelName) modelName.disabled = qwenSelected;
  if (triplePass) {
    triplePass.disabled = qwenSelected;
    if (qwenSelected) triplePass.checked = false;
  }
  [boostQuietSpeech, vadOnset, vadOffset].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (speakerCountFixButton) {
    speakerCountFixButton.disabled = qwenSelected;
    const speakerCountField = speakerCountFixButton.closest('.field');
    if (speakerCountField) speakerCountField.hidden = qwenSelected;
  }
  [minSpeakersField, maxSpeakersField].forEach(field => {
    if (field) field.hidden = qwenSelected || isSpeakerCountFixed();
  });
  [minSpeakersInput, maxSpeakersInput].forEach(input => {
    if (input) input.disabled = qwenSelected;
  });
  if (qwenBackendNote) qwenBackendNote.hidden = !qwenSelected;
  if (qwenVocabularyNote) qwenVocabularyNote.hidden = !qwenSelected;
}

function enabledTextDestinations() {
  const provider = aiProvider?.value || 'none';
  const mode = selectedTranscriptFinishingMode();
  if (provider === 'none' || mode === 'off') return [];
  const deferred = mode === 'recommended' && Boolean(finishInObsidian?.checked);
  const recommended = mode === 'recommended' && !deferred
    && Boolean(tokenConfigSnapshot.typesafe)
    && (document.querySelector('[name="ai_effort_cleanup"]')?.value || 'medium') !== 'off';
  const destinations = [];
  if (mode === 'advanced' || recommended || detectNames?.checked || createOutline?.checked) {
    destinations.push({provider, label: selectedOptionText(aiProvider), model: tokenConfigSnapshot[`${provider}_model`] || 'モデル未設定'});
  }
  if (recommended || (mode === 'advanced' && jevCompare?.checked)) {
    destinations.push({provider: 'typesafe', label: 'TypeSafe Jev（外部サービス）', model: tokenConfigSnapshot.typesafe_model || 'jev-latest'});
  }
  return destinations;
}

function createReadiness() {
  const blockers = [];
  const notes = [];
  let requiresModelAcknowledgement = false;
  if (configLoadState !== 'loaded') blockers.push(configLoadState === 'error' ? '設定を確認できません。接続と処理装置から再確認してください' : '実行環境と設定を確認中です');
  if (configLoadState === 'loaded') {
    const backend = transcriptionBackend?.value || 'whisperx';
    if (backend === 'whisperx' && !tokenConfigSnapshot.huggingface) blockers.push('話者分離に必要なHugging Faceトークンが未設定です');
    const readiness = tokenConfigSnapshot.transcription_readiness?.[backend];
    if (!readiness) blockers.push('方式・モデルの準備状態を取得できません。設定を再確認してください');
    else {
      blockers.push(...(readiness.blockers || []));
      notes.push(...(readiness.notes || []));
      requiresModelAcknowledgement = Boolean(readiness.notes?.length);
      const device = document.querySelector('#transcription-device')?.value || 'cpu';
      const model = readiness.models?.[device]?.[modelName?.value];
      if (model) {
        notes.push(`認識モデル: ${model.message}`);
        if (model.status !== 'cached') requiresModelAcknowledgement = true;
      } else if (backend === 'whisperx') {
        notes.push('選択した認識モデルの取得状況は未確認です');
        requiresModelAcknowledgement = true;
      }
    }
    enabledTextDestinations().forEach(destination => {
      if (!tokenConfigSnapshot[destination.provider]) blockers.push(`${destination.label}が未設定または接続できません`);
      if (destination.provider === 'lmstudio' && !tokenConfigSnapshot.lmstudio_model) blockers.push('ローカルLLMのモデルが未設定です');
    });
    if (selectedTranscriptFinishingMode() === 'advanced' && aiProvider?.value === 'none') blockers.push('全文仕上げに使うAIを選択してください');
  }
  if (typeof aiEffortReadiness === 'function') {
    const effortReadiness = aiEffortReadiness();
    blockers.push(...effortReadiness.blockers);
    notes.push(...effortReadiness.notes);
  }
  const acknowledged = Boolean(document.querySelector('#model-readiness-ack')?.checked);
  return {ready: hasSelectedSource() && !blockers.length && (!requiresModelAcknowledgement || acknowledged), requiresModelAcknowledgement, acknowledged, blockers: [...new Set(blockers)], notes: [...new Set(notes)]};
}

function updateCreateSummary() {
  const hasSource = hasSelectedSource();
  if (fileDropZone) fileDropZone.classList.toggle('has-file', hasSource);
  if (pathDetail) pathDetail.classList.toggle('selected', hasSource);

  const readiness = createReadiness();
  const readyMessage = !hasSource ? 'ファイルを選択してください'
    : readiness.blockers.length ? 'ファイル選択済み・開始前の確認が必要です'
    : readiness.requiresModelAcknowledgement ? 'ファイル選択済み・モデルの確認や取得が必要です' : 'ファイル選択済み・開始時にモデルを読み込みます';
  const modelAcknowledgement = document.querySelector('#model-readiness-ack-row');
  if (modelAcknowledgement) modelAcknowledgement.hidden = !readiness.requiresModelAcknowledgement;
  setAlert(document.querySelector('#setup-readiness-details'), [...readiness.blockers, ...readiness.notes].join('。'), Boolean(readiness.blockers.length));
  const destinations = enabledTextDestinations();
  const destinationText = destinations.length ? destinations.map(item => `${item.label} / ${item.model}`).join('、') : '送信なし';
  document.querySelectorAll('[data-text-destinations]').forEach(element => { element.textContent = `今回のテキスト送信先: ${destinationText}`; });
  const deferredNote = document.querySelector('#deferred-destination-note');
  if (deferredNote) deferredNote.hidden = !(finishInObsidian?.checked && selectedTranscriptFinishingMode() === 'recommended');
  if (setupReadyState) setupReadyState.textContent = readyMessage;
  document.querySelectorAll('[data-setup-ready]').forEach(element => { element.textContent = readyMessage; });

  const modePreset = conversationModePresets[selectedConversationMode()];
  const mode = modePreset ? modePreset.label : '会議モード';
  const qwenSelected = transcriptionBackend?.value === 'qwen3_nemotron';
  const model = qwenSelected
    ? 'Qwen3-ASR + ForcedAligner + Nemotron 3'
    : (selectedOptionText(modelName).split(' \u2014 ')[0] || '\u81ea\u52d5');
  const language = selectedOptionText(languageSelect) || '自動判定';
  const preprocess = selectedOptionText(audioPreprocess).split(' — ')[0] || 'おすすめ';
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');
  const transcriptionHardware = transcriptionDevice && transcriptionDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const diarizationHardware = diarizationDevice && diarizationDevice.value === 'cuda' ? 'GPU (CUDA)' : 'CPU';
  const vocabularyTerms = vocabularyTermsFromInput();
  const recognitionExtras = [];
  if (vocabularyTerms.length && !qwenSelected) recognitionExtras.push(`\u5358\u8a9e\u767b\u9332 ${vocabularyTerms.length}\u8a9e`);
  const fixedSpeakerLabel = isSpeakerCountFixed() ? `話者数 ${fixedSpeakerCountInput.value || '未入力'}人に固定` : '';
  if (fixedSpeakerLabel) recognitionExtras.push(fixedSpeakerLabel);
  const finishExtras = [];
  if (triplePass && triplePass.checked) finishExtras.push('詳細処理');
  const providerLabel = aiProvider && aiProvider.value !== 'none' ? selectedOptionText(aiProvider) : '';
  const finishingMode = selectedTranscriptFinishingMode();
  const finishInVault = Boolean(finishInObsidian && finishInObsidian.checked && finishingMode === 'recommended');
  const cleanupLevel = document.querySelector('[name="ai_effort_cleanup"]')?.value || 'medium';
  const recommendedCleanup = finishingMode === 'recommended' && !finishInVault
    && Boolean(tokenConfigSnapshot.typesafe) && cleanupLevel !== 'off';
  const otherAiWork = Boolean(detectNames && detectNames.checked);
  const notationWork = !finishInVault && (document.querySelector('[name="ai_effort_notation"]')?.value || 'off') !== 'off';
  const finishNow = Boolean(providerLabel) && finishingMode !== 'off'
    && (finishingMode === 'advanced' || recommendedCleanup || otherAiWork || notationWork);
  const configuredModel = finishNow ? String(tokenConfigSnapshot[`${aiProvider.value}_model`] || '').trim() : '';
  const finishingState = finishNow ? 'する' : 'しない';
  const finishingModel = finishNow
    ? `${providerLabel} / ${configuredModel || 'モデル未設定'}`
    : '使用モデルなし';
  const finishingDetail = finishInVault
    ? `${finishNow ? '話者を確認 / ' : ''}Obsidianに保存してあとで整える`
    : (finishNow ? (finishingMode === 'advanced' ? '全文を整える' : (recommendedCleanup ? '必要な箇所を整える' : '話者を確認する')) : '認識結果をそのまま残す');
  const finishingLabel = `${finishingState} / ${finishingModel}`;
  finishExtras.push(`AI仕上げ: ${finishingState}`);
  if (finishInVault) finishExtras.push('Obsidianに保存してあとで整える');
  if (jevCompare && jevCompare.checked) finishExtras.push('Jev修正要否比較');
  const emotionEnabled = Boolean(emotionAnalysis && emotionAnalysis.checked);
  if (emotionEnabled) finishExtras.push('感情分析');
  const emotionLabel = emotionEnabled ? (selectedOptionText(emotionModel).split('（')[0] || '実行する') : '実行しない';
  const outputParts = ['TXT', 'JSON'];
  const outputExtras = [];
  if (writeSrt && writeSrt.checked) { outputParts.push('SRT'); outputExtras.push('SRT'); }
  if (burnSubtitledVideo && burnSubtitledVideo.checked) { outputParts.push('字幕付き動画'); outputExtras.push('字幕付き動画'); }
  const extras = [...recognitionExtras, ...finishExtras, ...outputExtras];
  const engineLabel = qwenSelected ? model : `WhisperX / ${model}`;
  const summaryText = `${mode} / ${engineLabel} / ${language} / \u524d\u51e6\u7406: ${preprocess}${extras.length ? ` / ${extras.join(' / ')}` : ''}`;
  const launchText = `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}\u30fb${transcriptionHardware} / \u8a71\u8005\u5206\u96e2 ${diarizationHardware} / AI\u4ed5\u4e0a\u3052 ${finishingState}${finishInVault ? '\uff08\u3042\u3068\u3067Obsidian\uff09' : ''}`;
  if (setupSummary) setupSummary.textContent = launchText;
  document.querySelectorAll('[data-setup-summary]').forEach(element => { element.textContent = summaryText; });

  const selectedFile = inputFile && inputFile.files && inputFile.files[0];
  const directPath = sourcePath ? sourcePath.value.trim() : '';
  const sourceLabel = selectedFile
    ? selectedFile.name
    : (directPath ? directPath.split(/[\\/]/).pop() : '未選択');
  const setText = (selector, value) => {
    document.querySelectorAll(selector).forEach(element => { element.textContent = value; });
  };
  setText('[data-choice-transcription-device]', transcriptionHardware);
  setText('[data-choice-recognition-model]', `\u6587\u5b57\u8d77\u3053\u3057\u65b9\u5f0f ${engineLabel}`);
  setText('[data-choice-recognition-detail]', `話者分離 ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''} / ${language} / 前処理 ${preprocess}`);
  setText('[data-settings-value="vocabulary"]', vocabularyTerms.length ? `${vocabularyTerms.length}語を登録` : '未登録');
  setText('[data-choice-finishing-state]', finishingState);
  setText('[data-choice-finishing-model]', finishingModel);
  setText('[data-choice-finishing-detail]', finishingDetail);
  document.querySelectorAll('[data-choice-finishing-state]').forEach(element => element.classList.toggle('is-off', !finishNow));
  document.querySelectorAll('[data-open-panel="finishing"]').forEach(element => element.dataset.active = finishNow ? 'true' : 'false');
  setText('[data-settings-value="emotion"]', emotionLabel);
  setText('[data-settings-value="output"]', outputParts.join(' / '));
  setText('[data-review-source]', sourceLabel);
  setText('[data-review-transcription-compact]', `認識モデル ${model}・${transcriptionHardware} / 話者分離 ${diarizationHardware}`);
  setText('[data-review-transcription]', `認識モデル: ${model} / ${transcriptionHardware}`);
  setText('[data-review-diarization]', `話者分離: ${qwenSelected ? 'Nemotron 3' : 'pyannote.audio'} / ${diarizationHardware}${fixedSpeakerLabel ? ` / ${fixedSpeakerLabel}` : ''}`);
  setText('[data-review-finish]', `AI仕上げ ${finishingLabel}${finishInVault ? ' / Obsidianに保存してあとで整える' : ''}${emotionEnabled ? ` / 感情分析 ${emotionLabel}` : ''}`);
  setText('[data-review-output]', outputParts.join(' / '));
  setText('[data-flow-detail="1"]', hasSource ? sourceLabel : '未選択');
  setText('[data-flow-detail="2"]', `${mode} / ${model} / ${language}`);
  setText('[data-flow-detail="3"]', readiness.ready ? '開始時にモデル確認' : hasSource ? '開始前に要確認' : 'ファイルを選択');

  if (startButton) startButton.disabled = jobRunning || !readiness.ready;
  renderMobileWizard();
}

function isVideoSource(value) {
  return /\.(mp4|m4v|mov|mkv)$/i.test(String(value || '').trim().split(/[?#]/)[0]);
}

function hideSourcePreview() {
  window.clearTimeout(thumbnailTimer);
  thumbnailRequestId += 1;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = null;
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  if (sourceThumbnail) {
    sourceThumbnail.removeAttribute('src');
    sourceThumbnail.hidden = true;
  }
  if (sourcePreview) {
    sourcePreview.classList.remove('loaded');
    sourcePreview.hidden = true;
  }
  if (sourcePreviewMessage) sourcePreviewMessage.textContent = '';
}

async function showSourceThumbnail(path, name = '') {
  if (!sourcePreview || !sourceThumbnail || !sourcePreviewMessage) return;
  const value = String(path || '').trim();
  if (!isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  const requestId = ++thumbnailRequestId;
  if (sourceThumbnailController) sourceThumbnailController.abort();
  sourceThumbnailController = new AbortController();
  if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
  sourceThumbnailObjectUrl = null;
  sourcePreview.hidden = false;
  sourcePreview.classList.remove('loaded');
  sourceThumbnail.hidden = true;
  sourcePreviewMessage.textContent = `${name || value.split(/[\\/]/).pop()} のサムネイルを作成しています…`;
  sourceThumbnail.onload = () => {
    if (requestId !== thumbnailRequestId) return;
    if (sourceThumbnailObjectUrl) URL.revokeObjectURL(sourceThumbnailObjectUrl);
    sourceThumbnailObjectUrl = null;
    sourcePreview.classList.add('loaded');
    sourceThumbnail.hidden = false;
    sourcePreviewMessage.textContent = name || value;
  };
  const showThumbnailError = () => {
    if (requestId !== thumbnailRequestId) return;
    sourcePreview.classList.remove('loaded');
    sourceThumbnail.hidden = true;
    sourcePreviewMessage.textContent = 'サムネイルを作成できませんでした。動画として開けるファイルか確認してください。';
  };
  sourceThumbnail.onerror = showThumbnailError;
  try {
    const response = await apiFetch('/api/source-thumbnail', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: value}),
      cache: 'no-store',
      signal: sourceThumbnailController.signal
    });
    if (!response.ok) throw new Error('thumbnail request failed');
    const blob = await response.blob();
    if (requestId !== thumbnailRequestId) return;
    sourceThumbnailObjectUrl = URL.createObjectURL(blob);
    sourceThumbnail.src = sourceThumbnailObjectUrl;
  } catch (error) {
    if (error && error.name === 'AbortError') return;
    showThumbnailError();
  } finally {
    if (requestId === thumbnailRequestId) sourceThumbnailController = null;
  }
}

function scheduleSourceThumbnail(path) {
  window.clearTimeout(thumbnailTimer);
  const value = String(path || '').trim();
  if (!value || !isVideoSource(value)) {
    hideSourcePreview();
    return;
  }
  thumbnailTimer = window.setTimeout(() => showSourceThumbnail(value), 450);
}

function fallbackSpeaker(label) {
  if (!label || label === 'UNKNOWN') return '話者（未判定）';
  const match = String(label).match(/_(\d+)$/);
  return match ? `話者 ${Number(match[1]) + 1}` : label;
}

function hasUnsavedAnalysisChanges() {
  return Boolean(analysisState.dirty || preparationDirty);
}

// ---- Screens and routes (UX-01). Each screen owns one hash so reloads, the
// browser's back button and bookmarks return to the same place. ----
const viewRouteHashes = {new: '#/new', library: '#/data', analysis: '#/analysis', speakers: '#/speakers'};

function routeHash(view, id = '') {
  const encoded = id ? encodeURIComponent(String(id)) : '';
  if (view === 'item') return `#/data/${encoded}`;
  if (view === 'analysis' && encoded) return `#/analysis/${encoded}`;
  return viewRouteHashes[view] || '#/new';
}

function parseRouteHash(hash) {
  const parts = String(hash || '').replace(/^#\/?/, '').split('/').filter(Boolean).map(part => {
    try { return decodeURIComponent(part); } catch (_) { return part; }
  });
  const [head, id = ''] = parts;
  if (head === 'data' && id) return {view: 'item', itemId: id};
  if (head === 'data') return {view: 'library', itemId: ''};
  if (head === 'analysis') return {view: 'analysis', itemId: id};
  if (head === 'speakers') return {view: 'speakers', itemId: ''};
  if (head === 'new') return {view: 'new', itemId: ''};
  return null;
}

function syncRouteHash(hash, {replace = false} = {}) {
  currentRouteHash = hash;
  if (window.location.hash === hash) return;
  try {
    if (replace) window.history.replaceState(null, '', hash);
    else window.history.pushState(null, '', hash);
  } catch (_) {
    // Screens still switch when the history API is unavailable.
  }
}

// Every move between screens passes these checks, so unsaved edits are never
// dropped without asking (UX-30).
function confirmLeave({target, itemId = '', analysisItemId = ''}) {
  const resultVisible = resultCard && !resultCard.hidden;
  const sameItem = target === 'item' && itemId && currentJob && String(currentJob.id) === String(itemId);
  const leavingCurrentResult = currentJobDirty && !sameItem && (resultVisible || target === 'item');
  if (leavingCurrentResult && !window.confirm('文字起こし、会話プロファイル、または話者連携に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const leavingSpeakerManagement = target !== 'speakers'
    && speakerRegistryCard
    && !speakerRegistryCard.hidden
    && speakerRegistryDirty;
  if (leavingSpeakerManagement && !window.confirm('話者管理に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  const requestedAnalysisId = String(analysisItemId || '').trim();
  const analysisVisible = analysisCard && !analysisCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const leavingAnalysis = hasUnsavedAnalysisChanges()
    && (switchingAnalysisItem || (analysisVisible && target !== 'analysis'));
  if (leavingAnalysis && !window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。保存せずに移動しますか？')) {
    return false;
  }
  return true;
}

function loadAnalysisView(requestedItemId, {discardDirty = false} = {}) {
  if (!analysisCard) return;
  if (requestedItemId && analysisCatalogLoaded) {
    if (requestedItemId !== analysisState.itemId || !analysisState.data) {
      loadAnalysisItem(requestedItemId, {discardDirty});
    } else {
      if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
      const executionView = document.querySelector('#analysis-execution-view');
      if (executionView) executionView.hidden = true;
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
    }
    return;
  }
  if (requestedItemId) {
    analysisState.itemId = requestedItemId;
    analysisState.data = null;
    if (analysisItemSelect) analysisItemSelect.value = requestedItemId;
  }
  loadAnalysisCatalog();
}

function setActiveNavigation(view) {
  [
    [showNewButton, view === 'new'],
    [showLibraryButton, view === 'library' || view === 'item'],
    [showAnalysisButton, view === 'analysis'],
    [showSpeakersButton, view === 'speakers']
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
  [
    [showLibraryListButton, view === 'library'],
    [showLibraryAnalysisButton, view === 'analysis']
  ].forEach(([button, active]) => {
    if (!button) return;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

function showView(view, {analysisItemId = '', itemId = '', force = false, replace = false} = {}) {
  const target = ['new', 'library', 'analysis', 'speakers', 'item'].includes(view) ? view : 'new';
  const requestedAnalysisId = String(analysisItemId || '').trim();
  if (target === 'item' && !currentJob) return false;
  const targetItemId = target === 'item' ? String(itemId || currentJob.id) : '';
  if (!force && !confirmLeave({target, itemId: targetItemId, analysisItemId: requestedAnalysisId})) return false;
  const resultVisible = resultCard && !resultCard.hidden;
  const switchingAnalysisItem = target === 'analysis' && requestedAnalysisId && requestedAnalysisId !== analysisState.itemId;
  const contextChanged = document.body.dataset.view !== target || switchingAnalysisItem;
  const closedFixedViewer = contextChanged && typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = contextChanged && typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  const closedOrchestrationDialog = contextChanged && typeof closeAnalysisOrchestrationDialogs === 'function' && closeAnalysisOrchestrationDialogs();
  if (contextChanged) {
    analysisNavigationGeneration += 1;
    analysisSaveOwner = null;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
  }
  resultRequestSequence += 1;
  // A previous view's save cannot own this view's button or messages.
  if (saveButton) saveButton.disabled = false;
  if (resultVisible && currentJobDirty && target !== 'item') setCurrentJobDirty(false);
  if (target !== 'item' && mediaPlayer) mediaPlayer.pause();
  if (createView) createView.hidden = target !== 'new';
  if (processedDataHub) processedDataHub.hidden = !['library', 'analysis'].includes(target);
  if (libraryCard) libraryCard.hidden = target !== 'library';
  if (analysisCard) analysisCard.hidden = target !== 'analysis';
  if (speakerRegistryCard) speakerRegistryCard.hidden = target !== 'speakers';
  if (resultCard) resultCard.hidden = target !== 'item';
  document.body.dataset.view = target;
  setActiveNavigation(target);
  if (closedFixedViewer || closedAnalysisDialog || closedOrchestrationDialog) {
    const navigation = target === 'analysis' ? showAnalysisButton : target === 'speakers' ? showSpeakersButton
      : target === 'new' ? showNewButton : showLibraryButton;
    if (navigation?.isConnected && !navigation.closest('[hidden]')) navigation.focus();
  }
  if (target === 'analysis') loadAnalysisView(requestedAnalysisId, {discardDirty: force || Boolean(switchingAnalysisItem)});
  if (target === 'library') loadLibrary();
  if (target === 'speakers' && speakerRegistryCard) loadSpeakerRegistry();
  if (target === 'new') {
    renderMobileWizard();
    syncCreateViewState();
  }
  const hashId = target === 'item'
    ? targetItemId
    : (target === 'analysis' ? (requestedAnalysisId || analysisState.itemId) : '');
  syncRouteHash(routeHash(target, hashId), {replace});
  return true;
}

function openAnalysisForItem(itemId) {
  const targetItemId = String(itemId || '').trim();
  if (!targetItemId) return false;
  const returning = analysisEvidenceReturn?.itemId === targetItemId;
  const sameRevision = currentJob && analysisState.data
    && Number(currentJob.revision_count) === Number(analysisState.data.item.revision_count);
  if (returning && sameRevision) {
    analysisCatalog = analysisEvidenceReturn.catalog;
    analysisCatalogLoaded = true;
  }
  const opened = showView('analysis', {analysisItemId: targetItemId});
  if (opened && returning && sameRevision) {
    restoreAnalysisEvidencePosition();
    pollContentInsights();
  }
  return opened;
}

function openResultDestination(destination) {
  const target = String(destination || '').trim();
  if (target === 'analysis') return openAnalysisForItem(currentJobId);
  if (target === 'library' || target === 'speakers') return showView(target);
  return false;
}

// Tabs inside one record's workspace (UX-02): editing, conversation, summary, files.
function setItemTab(name) {
  const target = itemPanels.some(panel => panel.dataset.itemPanel === name) ? name : 'transcript';
  activeItemTab = target;
  itemPanels.forEach(panel => { panel.hidden = panel.dataset.itemPanel !== target; });
  itemTabButtons.forEach(button => {
    const active = button.dataset.itemTab === target;
    button.classList.toggle('active', active);
    button.setAttribute('aria-selected', String(active));
  });
}

// The header chip is the only job indicator outside the create screen (UX-16).
function updateJobChip(job) {
  if (!jobChip || !jobChipLabel) return;
  const status = job ? String(job.status || '') : '';
  const active = ['admitting', 'queued', 'running', 'committing'].includes(status);
  const pendingCompleted = Boolean(completedJob && job && completedJob.id === job.id && status === 'completed');
  const failed = ['failed', 'cancelled'].includes(status) && Boolean(progressCard && !progressCard.hidden);
  jobChip.hidden = !(active || pendingCompleted || failed);
  jobChip.classList.toggle('is-active', active);
  jobChip.classList.toggle('is-complete', pendingCompleted);
  jobChip.classList.toggle('has-error', failed);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', failed: 'エラー', cancelled: '中止しました'};
  if (active) jobChipLabel.textContent = `${titles[status] || '処理中'} ${Number(job.progress || 0)}%`;
  else if (pendingCompleted) jobChipLabel.textContent = '文字起こしが完了 — 結果を開く';
  else jobChipLabel.textContent = titles[status] || '処理状況';
}

function syncCreateViewState() {
  const progressVisible = Boolean(progressCard && !progressCard.hidden);
  if (form) form.hidden = jobRunning && progressVisible;
  const dismiss = document.querySelector('#progress-dismiss');
  if (dismiss) dismiss.hidden = jobRunning || !progressVisible;
  updateJobChip(lastProgressJob);
}

function showProgressCard({scroll = false} = {}) {
  if (!progressCard) return;
  progressCard.hidden = false;
  syncCreateViewState();
  if (scroll && createView && !createView.hidden) {
    progressCard.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
  }
}

listen(showLibraryButton, 'click', () => showView('library'));
listen(showAnalysisButton, 'click', () => showView('analysis'));
listen(showLibraryListButton, 'click', () => showView('library'));
listen(showLibraryAnalysisButton, 'click', () => showView('analysis'));
listen(showNewButton, 'click', () => showView('new'));
listen(showSpeakersButton, 'click', () => showView('speakers'));
itemTabButtons.forEach(button => listen(button, 'click', () => setItemTab(button.dataset.itemTab)));
listen(jobChip, 'click', () => {
  if (completedJob) {
    const job = completedJob;
    if (!confirmLeave({target: 'item', itemId: job.id})) return;
    completedJob = null;
    renderResult(job);
    return;
  }
  if (showView('new') && progressCard && !progressCard.hidden) {
    progressCard.scrollIntoView({behavior: scrollBehavior(), block: 'start'});
  }
});
listen(document.querySelector('#progress-dismiss'), 'click', () => {
  if (jobRunning || !progressCard) return;
  progressCard.hidden = true;
  lastProgressJob = null;
  syncCreateViewState();
});
const connectionDialog = document.querySelector('#connection-dialog');
listen(document.querySelector('#connection-button'), 'click', () => {
  if (connectionDialog && typeof connectionDialog.showModal === 'function' && !connectionDialog.open) {
    connectionDialog.showModal();
  }
});
listen(document.querySelector('#analysis-open-item-button'), 'click', () => {
  const itemId = analysisState.itemId;
  if (!itemId) return;
  if (currentJob && String(currentJob.id) === String(itemId)) {
    showView('item', {itemId});
    return;
  }
  if (!confirmLeave({target: 'item', itemId})) return;
  openLibraryItem(itemId);
});

// Tablists follow the WAI-ARIA tabs pattern (UX-23): one Tab stop per list on the
// selected tab, and arrow/Home/End keys move focus between tabs. Activation stays
// on Enter/Space because switching views can ask about unsaved changes.
function syncTabStops() {
  document.querySelectorAll('[role="tablist"]').forEach(tablist => {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')];
    const selected = tabs.find(tab => tab.getAttribute('aria-selected') === 'true') || tabs[0];
    tabs.forEach(tab => tab.setAttribute('tabindex', tab === selected ? '0' : '-1'));
  });
}
document.querySelectorAll('[role="tablist"]').forEach(tablist => {
  listen(tablist, 'keydown', event => {
    const tabs = [...tablist.querySelectorAll('[role="tab"]')].filter(tab => !tab.hidden && !tab.disabled);
    const index = tabs.indexOf(document.activeElement);
    const targets = {ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1};
    if (index < 0 || !(event.key in targets)) return;
    event.preventDefault();
    tabs[(targets[event.key] + tabs.length) % tabs.length].focus();
  });
});
new MutationObserver(syncTabStops).observe(document.body, {subtree: true, attributeFilter: ['aria-selected']});
syncTabStops();

window.addEventListener('beforeunload', event => {
  if (!currentJobDirty && !speakerRegistryDirty && !analysisState.dirty && !preparationDirty) return;
  event.preventDefault();
  event.returnValue = '';
});

function newLocalSpeakerId() {
  return self.crypto && self.crypto.randomUUID
    ? self.crypto.randomUUID().replaceAll('-', '')
    : `speaker_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function blankSpeakerRecord() {
  return {
    id: newLocalSpeakerId(),
    participant_code: '',
    display_name: '',
    pseudonym: '',
    default_role: 'participant',
    organization: '',
    department: '',
    job_title: '',
    confidentiality_status: 'unknown',
    tags: [],
    attributes: {},
    notes: '',
    active: true
  };
}

function attributesToText(attributes) {
  return Object.entries(attributes || {}).map(([key, value]) => `${key}=${value}`).join('; ');
}

function textToAttributes(value) {
  const attributes = {};
  String(value || '').split(/[;\n]+/).forEach(part => {
    const separator = part.includes('=') ? '=' : ':';
    const index = part.indexOf(separator);
    if (index <= 0) return;
    const key = part.slice(0, index).trim();
    const itemValue = part.slice(index + 1).trim();
    if (key) attributes[key] = itemValue;
  });
  return attributes;
}

function speakerSurveyQuestionKeys(records = speakerRegistry) {
  const keys = new Set();
  records.forEach(record => {
    const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
    Object.keys(attributes || {}).forEach(key => {
      const clean = String(key || '').trim();
      if (clean) keys.add(clean);
    });
  });
  return [...keys].sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}));
}

function speakerSurveyAnswer(record, question) {
  const attributes = record && typeof record.attributes === 'object' ? record.attributes : {};
  return String((attributes || {})[question] ?? '').trim();
}

function speakerSurveyQuestionSummary(records, question) {
  const counts = new Map();
  const answeredRecords = [];
  records.forEach(record => {
    const answer = speakerSurveyAnswer(record, question);
    if (!answer) return;
    answeredRecords.push(record);
    counts.set(answer, (counts.get(answer) || 0) + 1);
  });
  const values = [...counts.entries()]
    .map(([value, count]) => ({value, count}))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value, 'ja', {numeric: true}));
  return {
    question,
    answeredRecords,
    answered: answeredRecords.length,
    missing: Math.max(0, records.length - answeredRecords.length),
    values
  };
}

function speakerSurveyNumericValue(value) {
  const normalized = String(value || '').trim().normalize('NFKC').replaceAll(',', '');
  if (/^[+-]?(?:\d+(?:\.\d+)?|\.\d+)$/.test(normalized)) return Number(normalized);
  const scale = normalized.match(/^([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*[:：]/);
  return scale ? Number(scale[1]) : null;
}

function speakerSurveyNumericSummary(records, question) {
  const values = records
    .map(record => speakerSurveyNumericValue(speakerSurveyAnswer(record, question)))
    .filter(Number.isFinite)
    .sort((a, b) => a - b);
  const answered = records.filter(record => speakerSurveyAnswer(record, question)).length;
  if (values.length < 2 || values.length < answered * 0.8) return null;
  const middle = Math.floor(values.length / 2);
  const median = values.length % 2 ? values[middle] : (values[middle - 1] + values[middle]) / 2;
  return {
    count: values.length,
    mean: values.reduce((sum, value) => sum + value, 0) / values.length,
    median,
    minimum: values[0],
    maximum: values[values.length - 1]
  };
}

function speakerSurveyCorrelation(records, questionA, questionB) {
  const pairs = records.map(record => [
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionA)),
    speakerSurveyNumericValue(speakerSurveyAnswer(record, questionB))
  ]).filter(([a, b]) => Number.isFinite(a) && Number.isFinite(b));
  if (pairs.length < 3) return null;
  const meanA = pairs.reduce((sum, pair) => sum + pair[0], 0) / pairs.length;
  const meanB = pairs.reduce((sum, pair) => sum + pair[1], 0) / pairs.length;
  const numerator = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) * (pair[1] - meanB), 0);
  const denominatorA = pairs.reduce((sum, pair) => sum + (pair[0] - meanA) ** 2, 0);
  const denominatorB = pairs.reduce((sum, pair) => sum + (pair[1] - meanB) ** 2, 0);
  const denominator = Math.sqrt(denominatorA * denominatorB);
  if (!denominator) return null;
  return {count: pairs.length, coefficient: numerator / denominator};
}

function scheduleSpeakerSurveyAnalysis() {
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = window.setTimeout(renderSpeakerSurveyAnalysis, 160);
}

function appendSpeakerSurveyBar(container, label, count, total, maximum) {
  const row = analysisElement('div', 'speaker-survey-bar');
  const heading = analysisElement('div');
  heading.append(
    analysisElement('strong', '', label),
    analysisElement('span', '', `${count}人 / ${total ? (100 * count / total).toFixed(1) : '0.0'}%`)
  );
  const track = analysisElement('div', 'speaker-survey-bar-track');
  const fill = analysisElement('i');
  fill.style.width = `${maximum ? (100 * count / maximum).toFixed(2) : 0}%`;
  track.append(fill);
  row.append(heading, track);
  container.append(row);
}

function buildSpeakerSurveyCompleteness(records, questions) {
  const panel = analysisElement('section', 'speaker-survey-panel');
  panel.append(
    analysisElement('h4', '', '質問別の回答率'),
    analysisElement('p', 'speaker-survey-help', '')
  );
  panel.lastChild.textContent = '回答漏れの確認と、分析対象にする質問の選択ができます。';
  const list = analysisElement('div', 'speaker-survey-completeness');
  questions
    .map(question => speakerSurveyQuestionSummary(records, question))
    .sort((a, b) => b.answered - a.answered || a.question.localeCompare(b.question, 'ja'))
    .forEach(summary => {
      const button = analysisElement('button', summary.question === speakerSurveyAnalysisState.primaryQuestion ? 'active' : '');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(summary.question === speakerSurveyAnalysisState.primaryQuestion));
      const text = analysisElement('span');
      text.append(
        analysisElement('strong', '', summary.question),
        analysisElement('small', '', `${summary.answered} / ${records.length}人`)
      );
      const track = analysisElement('i');
      const fill = analysisElement('b');
      fill.style.width = `${records.length ? (100 * summary.answered / records.length).toFixed(2) : 0}%`;
      track.append(fill);
      button.append(text, track);
      button.addEventListener('click', () => {
        speakerSurveyAnalysisState.primaryQuestion = summary.question;
        speakerSurveyAnalysisState.answerFilter = '';
        if (speakerSurveyAnalysisState.secondaryQuestion === summary.question) {
          speakerSurveyAnalysisState.secondaryQuestion = questions.find(item => item !== summary.question) || '';
        }
        renderSpeakerSurveyAnalysis();
      });
      list.append(button);
    });
  panel.append(list);
  return panel;
}

function buildSpeakerSurveyCrosstab(records, primaryQuestion, secondaryQuestion) {
  const panel = analysisElement('section', 'speaker-survey-panel speaker-survey-crosstab');
  panel.append(
    analysisElement('h4', '', '2項目クロス集計'),
    analysisElement('p', 'speaker-survey-help', `${primaryQuestion} × ${secondaryQuestion} の組み合わせ人数と行内割合です。`)
  );
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  const secondary = speakerSurveyQuestionSummary(records, secondaryQuestion);
  const rowValues = primary.values.slice(0, 12).map(item => item.value);
  const columnValues = secondary.values.slice(0, 10).map(item => item.value);
  if (!rowValues.length || !columnValues.length) {
    panel.append(analysisElement('p', 'analysis-no-data', 'クロス集計できる回答がありません。'));
    return panel;
  }
  const wrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  headRow.append(analysisElement('th', '', primaryQuestion));
  columnValues.forEach(value => headRow.append(analysisElement('th', '', value)));
  headRow.append(analysisElement('th', '', '合計'));
  head.append(headRow);
  const body = document.createElement('tbody');
  rowValues.forEach(rowValue => {
    const row = document.createElement('tr');
    row.append(analysisElement('th', '', rowValue));
    const rowTotal = records.filter(record => speakerSurveyAnswer(record, primaryQuestion) === rowValue).length;
    columnValues.forEach(columnValue => {
      const count = records.filter(record => (
        speakerSurveyAnswer(record, primaryQuestion) === rowValue
        && speakerSurveyAnswer(record, secondaryQuestion) === columnValue
      )).length;
      const cell = analysisElement('td', count ? 'has-value' : '', count
        ? `${count}（${rowTotal ? (100 * count / rowTotal).toFixed(0) : 0}%）`
        : '—');
      if (count) cell.style.setProperty('--survey-cell-strength', String(count / Math.max(1, rowTotal)));
      row.append(cell);
    });
    row.append(analysisElement('td', 'total', String(rowTotal)));
    body.append(row);
  });
  table.append(head, body);
  wrap.append(table);
  panel.append(wrap);
  if (primary.values.length > rowValues.length || secondary.values.length > columnValues.length) {
    panel.append(analysisElement('p', 'speaker-survey-note', '表示量を抑えるため、回答数が多い選択肢を優先して表示しています。'));
  }
  const correlation = speakerSurveyCorrelation(records, primaryQuestion, secondaryQuestion);
  if (correlation) {
    const correlationBox = analysisElement('div', 'speaker-survey-correlation');
    correlationBox.append(
      analysisElement('span', '', '数値回答の相関'),
      analysisElement('strong', '', `r = ${correlation.coefficient.toFixed(3)}`),
      analysisElement('small', '', `n = ${correlation.count}。関連の強さを示す記述値で、因果関係は示しません。`)
    );
    panel.append(correlationBox);
  }
  return panel;
}

function renderSpeakerSurveyAnalysis() {
  const container = document.querySelector('#speaker-survey-analysis-content');
  if (!container) return;
  window.clearTimeout(speakerSurveyAnalysisTimer);
  speakerSurveyAnalysisTimer = null;
  const allQuestions = speakerSurveyQuestionKeys(speakerRegistry);
  const metric = document.querySelector('#registry-survey-metric');
  if (metric) metric.textContent = String(allQuestions.length);
  container.replaceChildren();
  if (!allQuestions.length) {
    const empty = analysisElement('div', 'speaker-survey-empty');
    empty.append(
      analysisElement('strong', '', '事前アンケート回答がまだありません'),
      analysisElement('p', '', 'Googleフォームの回答CSVを読み込むか、各話者の「事前アンケート回答」に「質問=回答」の形式で入力してください。')
    );
    container.append(empty);
    return;
  }

  const records = speakerSurveyAnalysisState.includeInactive
    ? [...speakerRegistry]
    : speakerRegistry.filter(record => record.active !== false);
  if (!allQuestions.includes(speakerSurveyAnalysisState.primaryQuestion)) {
    speakerSurveyAnalysisState.primaryQuestion = allQuestions[0];
  }
  if (
    !allQuestions.includes(speakerSurveyAnalysisState.secondaryQuestion)
    || speakerSurveyAnalysisState.secondaryQuestion === speakerSurveyAnalysisState.primaryQuestion
  ) {
    speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(
      question => question !== speakerSurveyAnalysisState.primaryQuestion
    ) || '';
  }
  const primaryQuestion = speakerSurveyAnalysisState.primaryQuestion;
  const primary = speakerSurveyQuestionSummary(records, primaryQuestion);
  if (
    speakerSurveyAnalysisState.answerFilter
    && !primary.values.some(item => item.value === speakerSurveyAnalysisState.answerFilter)
  ) {
    speakerSurveyAnalysisState.answerFilter = '';
  }

  const controls = analysisElement('div', 'speaker-survey-controls');
  const primaryLabel = analysisElement('label', 'field');
  primaryLabel.append(analysisElement('span', '', '分析する質問'));
  const primarySelect = document.createElement('select');
  allQuestions.forEach(question => primarySelect.add(new Option(question, question)));
  primarySelect.value = primaryQuestion;
  primarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.primaryQuestion = primarySelect.value;
    speakerSurveyAnalysisState.answerFilter = '';
    if (speakerSurveyAnalysisState.secondaryQuestion === primarySelect.value) {
      speakerSurveyAnalysisState.secondaryQuestion = allQuestions.find(question => question !== primarySelect.value) || '';
    }
    renderSpeakerSurveyAnalysis();
  });
  primaryLabel.append(primarySelect);

  const secondaryLabel = analysisElement('label', 'field');
  secondaryLabel.append(analysisElement('span', '', 'クロス集計する質問'));
  const secondarySelect = document.createElement('select');
  secondarySelect.add(new Option('クロス集計しない', ''));
  allQuestions.filter(question => question !== primaryQuestion)
    .forEach(question => secondarySelect.add(new Option(question, question)));
  secondarySelect.value = speakerSurveyAnalysisState.secondaryQuestion;
  secondarySelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.secondaryQuestion = secondarySelect.value;
    renderSpeakerSurveyAnalysis();
  });
  secondaryLabel.append(secondarySelect);

  const filterLabel = analysisElement('label', 'field');
  filterLabel.append(analysisElement('span', '', '回答で参加者を絞り込み'));
  const answerSelect = document.createElement('select');
  answerSelect.add(new Option('すべての回答', ''));
  primary.values.forEach(item => answerSelect.add(new Option(`${item.value}（${item.count}人）`, item.value)));
  answerSelect.value = speakerSurveyAnalysisState.answerFilter;
  answerSelect.addEventListener('change', () => {
    speakerSurveyAnalysisState.answerFilter = answerSelect.value;
    renderSpeakerSurveyAnalysis();
  });
  filterLabel.append(answerSelect);

  const inactiveLabel = analysisElement('label', 'mini-check speaker-survey-inactive');
  const inactive = document.createElement('input');
  inactive.type = 'checkbox';
  inactive.checked = speakerSurveyAnalysisState.includeInactive;
  inactive.addEventListener('change', () => {
    speakerSurveyAnalysisState.includeInactive = inactive.checked;
    speakerSurveyAnalysisState.answerFilter = '';
    renderSpeakerSurveyAnalysis();
  });
  inactiveLabel.append(inactive, document.createTextNode('無効な話者を含める'));
  controls.append(primaryLabel, secondaryLabel, filterLabel, inactiveLabel);
  container.append(controls);

  const overview = analysisElement('div', 'speaker-survey-overview');
  const responseRate = records.length ? 100 * primary.answered / records.length : 0;
  [
    ['分析対象', `${records.length}人`, speakerSurveyAnalysisState.includeInactive ? '全登録話者' : '有効な話者'],
    ['質問項目', `${allQuestions.length}問`, 'CSVの未知列を含む'],
    ['回答済み', `${primary.answered}人`, `${responseRate.toFixed(1)}%`],
    ['未回答', `${primary.missing}人`, primary.missing ? '回答漏れを確認' : '回答完了']
  ].forEach(([label, value, note]) => {
    const item = analysisElement('div');
    item.append(
      analysisElement('span', '', label),
      analysisElement('strong', '', value),
      analysisElement('small', '', note)
    );
    overview.append(item);
  });
  container.append(overview);

  const grid = analysisElement('div', 'speaker-survey-grid');
  const distributionPanel = analysisElement('section', 'speaker-survey-panel');
  distributionPanel.append(
    analysisElement('h4', '', `回答分布：${primaryQuestion}`),
    analysisElement('p', 'speaker-survey-help', '同じ回答をまとめ、回答者全体に占める割合を表示します。')
  );
  const distribution = analysisElement('div', 'speaker-survey-bars');
  const maximum = Math.max(0, ...primary.values.map(item => item.count));
  primary.values.slice(0, 20).forEach(item => {
    appendSpeakerSurveyBar(distribution, item.value, item.count, primary.answered, maximum);
  });
  if (!primary.values.length) distribution.append(analysisElement('p', 'analysis-no-data', 'この質問への回答がありません。'));
  distributionPanel.append(distribution);
  if (primary.values.length > 20) {
    distributionPanel.append(analysisElement('p', 'speaker-survey-note', `回答数上位20件を表示（全${primary.values.length}種類）`));
  }
  const numeric = speakerSurveyNumericSummary(records, primaryQuestion);
  if (numeric) {
    const numericBox = analysisElement('div', 'speaker-survey-numeric');
    [
      ['平均', numeric.mean.toFixed(2)],
      ['中央値', numeric.median.toFixed(2)],
      ['最小', numeric.minimum.toFixed(2)],
      ['最大', numeric.maximum.toFixed(2)]
    ].forEach(([label, value]) => {
      const item = analysisElement('span');
      item.append(analysisElement('small', '', label), document.createTextNode(value));
      numericBox.append(item);
    });
    numericBox.append(analysisElement('p', '', `数値として解釈できた回答 n=${numeric.count}`));
    distributionPanel.append(numericBox);
  }
  grid.append(distributionPanel, buildSpeakerSurveyCompleteness(records, allQuestions));
  container.append(grid);

  if (speakerSurveyAnalysisState.secondaryQuestion) {
    container.append(buildSpeakerSurveyCrosstab(
      records,
      primaryQuestion,
      speakerSurveyAnalysisState.secondaryQuestion
    ));
  }

  const participantPanel = analysisElement('section', 'speaker-survey-panel speaker-survey-participants');
  const selectedRecords = records.filter(record => (
    !speakerSurveyAnalysisState.answerFilter
    || speakerSurveyAnswer(record, primaryQuestion) === speakerSurveyAnalysisState.answerFilter
  ));
  participantPanel.append(
    analysisElement('h4', '', `該当参加者（${selectedRecords.length}人）`),
    analysisElement('p', 'speaker-survey-help', speakerSurveyAnalysisState.answerFilter
      ? `「${speakerSurveyAnalysisState.answerFilter}」と回答した参加者です。`
      : '回答内容と参加者を照合できます。氏名より仮名・参加者コードの利用を推奨します。')
  );
  const tableWrap = analysisElement('div', 'speaker-survey-table-wrap');
  const table = document.createElement('table');
  table.className = 'speaker-survey-table participant';
  const head = document.createElement('thead');
  const headRow = document.createElement('tr');
  ['参加者', '参加者コード', primaryQuestion, speakerSurveyAnalysisState.secondaryQuestion].filter(Boolean)
    .forEach(label => headRow.append(analysisElement('th', '', label)));
  head.append(headRow);
  const body = document.createElement('tbody');
  selectedRecords.slice(0, 100).forEach(record => {
    const row = document.createElement('tr');
    [
      speakerRecordName(record),
      record.participant_code || '—',
      speakerSurveyAnswer(record, primaryQuestion) || '未回答',
      speakerSurveyAnalysisState.secondaryQuestion
        ? speakerSurveyAnswer(record, speakerSurveyAnalysisState.secondaryQuestion) || '未回答'
        : null
    ].filter(value => value !== null).forEach(value => row.append(analysisElement('td', '', value)));
    body.append(row);
  });
  table.append(head, body);
  tableWrap.append(table);
  participantPanel.append(tableWrap);
  if (selectedRecords.length > 100) {
    participantPanel.append(analysisElement('p', 'speaker-survey-note', '画面には先頭100人を表示しています。全件はCSV書き出しで確認できます。'));
  }
  container.append(participantPanel);
}

function setSpeakerRegistryDirty(dirty = true, trackMutation = true) {
  speakerRegistryDirty = dirty;
  if (speakerRegistryDirty && trackMutation) speakerRegistryMutationGeneration += 1;
  const metric = document.querySelector('#registry-dirty-metric');
  if (metric) {
    metric.textContent = dirty ? '未保存' : '保存済み';
    metric.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveState) {
    speakerRegistrySaveState.textContent = dirty ? '未保存の変更があります' : '保存済み';
    speakerRegistrySaveState.classList.toggle('unsaved', dirty);
  }
  if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !dirty || speakerRegistrySaveInProgress;
  if (speakerRegistryCard) speakerRegistryCard.classList.toggle('has-unsaved', dirty);
  scheduleSpeakerSurveyAnalysis();
}

function makeSheetInput(record, key, {
  type = 'text', wide = false, multiline = false, label = '', placeholder = '', afterInput = null
} = {}) {
  const input = document.createElement(multiline ? 'textarea' : 'input');
  if (!multiline) input.type = type;
  if (wide) input.className = 'cell-wide';
  if (label) input.setAttribute('aria-label', label);
  if (placeholder) input.placeholder = placeholder;
  input.dataset.speakerId = record.id;
  input.dataset.speakerField = key;
  input.value = Array.isArray(record[key]) ? record[key].join(', ') : (record[key] || '');
  input.addEventListener('input', () => {
    record[key] = key === 'tags'
      ? input.value.split(/[,、;]+/).map(item => item.trim()).filter(Boolean)
      : input.value;
    setSpeakerRegistryDirty();
    if (afterInput) afterInput(input.value);
  });
  return input;
}

function makeSheetSelect(record, key, labels, {label = '', afterChange = null} = {}) {
  const select = document.createElement('select');
  if (label) select.setAttribute('aria-label', label);
  select.dataset.speakerId = record.id;
  select.dataset.speakerField = key;
  Object.entries(labels).forEach(([value, label]) => select.add(new Option(label, value)));
  select.value = record[key] || Object.keys(labels)[0];
  select.addEventListener('change', () => {
    record[key] = select.value;
    setSpeakerRegistryDirty();
    if (afterChange) afterChange(select.value);
  });
  return select;
}

function appendSheetCell(row, control) {
  const cell = document.createElement('td');
  cell.append(control);
  row.append(cell);
}

async function loadSpeakerRegistry(force = false) {
  if (speakerRegistryLoaded && !force) {
    renderSpeakerRegistry();
    return speakerRegistry;
  }
  try {
    const response = await apiFetch('/api/speakers', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '話者管理データを取得できませんでした。');
    speakerRegistry = Array.isArray(data.speakers) ? data.speakers : [];
    speakerRegistryBaseline = deepCopy(speakerRegistry);
    speakerSaveConflict = false;
    document.querySelector('#speaker-draft-recovery').hidden = true;
    speakerRegistryRevision = Number(data.registry_revision || 0);
    speakerRegistryDeletedIds.clear();
    speakerRegistryLoaded = true;
    setSpeakerRegistryDirty(false);
    renderSpeakerRegistry();
    if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    return speakerRegistry;
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
    return [];
  }
}

function speakerRecordName(record) {
  return String(record.pseudonym || record.display_name || record.participant_code || '名前未設定').trim();
}

function speakerRecordSearchText(record) {
  return [
    record.participant_code, record.display_name, record.pseudonym, record.organization,
    record.department, record.job_title, ...(record.tags || []),
    ...Object.entries(record.attributes || {}).flat(), record.notes
  ].join(' ').toLocaleLowerCase();
}

function visibleSpeakerRegistry() {
  const searchElement = document.querySelector('#speaker-registry-search');
  const roleElement = document.querySelector('#speaker-registry-role-filter');
  const showInactiveElement = document.querySelector('#speaker-registry-show-inactive');
  const query = (searchElement ? searchElement.value : '').trim().toLocaleLowerCase();
  const role = roleElement ? roleElement.value : '';
  const showInactive = !showInactiveElement || showInactiveElement.checked;
  return speakerRegistry.filter(record => {
    if (!showInactive && !record.active) return false;
    if (role && record.default_role !== role) return false;
    if (!query) return true;
    return speakerRecordSearchText(record).includes(query);
  });
}

function updateSpeakerRegistryOverview() {
  const active = speakerRegistry.filter(record => record.active !== false);
  const values = {
    '#registry-total-metric': speakerRegistry.length,
    '#registry-active-metric': active.length,
    '#registry-survey-metric': speakerSurveyQuestionKeys(speakerRegistry).length
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = String(value);
  });
}

function removeSpeakerRecord(record) {
  if (!window.confirm(`${speakerRecordName(record)} を話者管理から削除しますか？\n「変更を保存」するまで削除は確定しません。`)) return;
  speakerRegistryDeletedIds.add(record.id);
  speakerRegistry = speakerRegistry.filter(item => item.id !== record.id);
  setSpeakerRegistryDirty();
  renderSpeakerRegistry();
}

function makeAttributesControl(record, label) {
  const attributes = document.createElement('textarea');
  attributes.value = attributesToText(record.attributes);
  attributes.placeholder = '例：満足度=5; 年齢層=30代; 利用歴=3年以上';
  attributes.setAttribute('aria-label', label);
  attributes.dataset.speakerId = record.id;
  attributes.dataset.speakerField = 'attributes';
  attributes.addEventListener('input', () => {
    record.attributes = textToAttributes(attributes.value);
    setSpeakerRegistryDirty();
  });
  return attributes;
}

function renderSpeakerRegistryTable(visible) {
  speakerRegistryBody.replaceChildren();
  if (!visible.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 13;
    cell.className = 'speaker-registry-empty';
    cell.textContent = '条件に一致する話者はいません。検索条件を変えるか、新しい話者を追加してください。';
    row.append(cell);
    speakerRegistryBody.append(row);
    return;
  }

  visible.forEach(record => {
    const row = document.createElement('tr');
    row.dataset.speakerId = record.id;
    row.classList.toggle('inactive', !record.active);
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    active.addEventListener('change', () => {
      record.active = active.checked;
      setSpeakerRegistryDirty();
      row.classList.toggle('inactive', !record.active);
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });
    appendSheetCell(row, active);
    appendSheetCell(row, makeSheetInput(record, 'participant_code', {label: `${speakerRecordName(record)}の参加者コード`}));
    appendSheetCell(row, makeSheetInput(record, 'display_name', {label: `${speakerRecordName(record)}の氏名`}));
    appendSheetCell(row, makeSheetInput(record, 'pseudonym', {label: `${speakerRecordName(record)}の仮名・表示名`}));
    appendSheetCell(row, makeSheetSelect(record, 'default_role', speakerRoleLabels, {
      label: `${speakerRecordName(record)}の既定役割`,
      afterChange: () => {
        const roleFilter = document.querySelector('#speaker-registry-role-filter');
        if (roleFilter && roleFilter.value) renderSpeakerRegistry();
      }
    }));
    appendSheetCell(row, makeSheetInput(record, 'organization', {label: `${speakerRecordName(record)}の組織`}));
    appendSheetCell(row, makeSheetInput(record, 'department', {label: `${speakerRecordName(record)}の部署`}));
    appendSheetCell(row, makeSheetInput(record, 'job_title', {label: `${speakerRecordName(record)}の役職`}));
    appendSheetCell(row, makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: `${speakerRecordName(record)}の守秘同意`}));
    appendSheetCell(row, makeSheetInput(record, 'tags', {wide: true, label: `${speakerRecordName(record)}のタグ`}));
    appendSheetCell(row, makeAttributesControl(record, `${speakerRecordName(record)}の事前アンケート回答`));
    appendSheetCell(row, makeSheetInput(record, 'notes', {multiline: true, label: `${speakerRecordName(record)}の備考`}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${speakerRecordName(record)}を削除`);
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    appendSheetCell(row, remove);
    speakerRegistryBody.append(row);
  });
}

function createSpeakerCardField(labelText, control, wide = false) {
  const label = document.createElement('label');
  label.className = `field speaker-card-field${wide ? ' wide' : ''}`;
  const text = document.createElement('span');
  text.textContent = labelText;
  label.append(text, control);
  return label;
}

function renderSpeakerRegistryCards(visible) {
  speakerRegistryList.replaceChildren();
  if (!visible.length) {
    const empty = document.createElement('div');
    empty.className = 'speaker-registry-empty';
    empty.textContent = '条件に一致する話者はいません。条件をクリアするか、新しい話者を追加してください。';
    speakerRegistryList.append(empty);
    return;
  }

  visible.forEach(record => {
    const card = document.createElement('article');
    card.className = 'speaker-management-card';
    card.dataset.speakerId = record.id;
    card.classList.toggle('inactive', record.active === false);

    const header = document.createElement('header');
    const identity = document.createElement('div');
    const role = document.createElement('span');
    role.className = 'speaker-card-role';
    const title = document.createElement('h3');
    const subtitle = document.createElement('p');
    identity.append(role, title, subtitle);
    const activeLabel = document.createElement('label');
    activeLabel.className = 'speaker-card-active';
    const active = document.createElement('input');
    active.type = 'checkbox';
    active.checked = record.active !== false;
    const activeText = document.createElement('span');
    activeText.textContent = '有効';
    activeLabel.append(active, activeText);
    header.append(identity, activeLabel);

    const refreshIdentity = () => {
      role.textContent = speakerRoleLabels[record.default_role] || 'その他';
      title.textContent = speakerRecordName(record);
      subtitle.textContent = [record.participant_code, record.organization, record.job_title].filter(Boolean).join(' ・ ') || '基本情報を入力してください';
      active.setAttribute('aria-label', `${speakerRecordName(record)}を有効にする`);
    };
    refreshIdentity();
    active.addEventListener('change', () => {
      record.active = active.checked;
      card.classList.toggle('inactive', !active.checked);
      setSpeakerRegistryDirty();
      updateSpeakerRegistryOverview();
      const showInactive = document.querySelector('#speaker-registry-show-inactive');
      if (!active.checked && showInactive && !showInactive.checked) renderSpeakerRegistry();
    });

    const primary = document.createElement('div');
    primary.className = 'speaker-card-grid primary';
    primary.append(
      createSpeakerCardField('参加者コード', makeSheetInput(record, 'participant_code', {label: '参加者コード', afterInput: refreshIdentity})),
      createSpeakerCardField('氏名', makeSheetInput(record, 'display_name', {label: '氏名', afterInput: refreshIdentity})),
      createSpeakerCardField('仮名・表示名', makeSheetInput(record, 'pseudonym', {label: '仮名・表示名', afterInput: refreshIdentity})),
      createSpeakerCardField('既定役割', makeSheetSelect(record, 'default_role', speakerRoleLabels, {
        label: '既定役割', afterChange: () => {
          refreshIdentity();
          const roleFilter = document.querySelector('#speaker-registry-role-filter');
          if (roleFilter && roleFilter.value) renderSpeakerRegistry();
        }
      }))
    );

    const details = document.createElement('details');
    details.className = 'speaker-card-details';
    const summary = document.createElement('summary');
    summary.textContent = '所属・アンケート・詳細を編集';
    const detailGrid = document.createElement('div');
    detailGrid.className = 'speaker-card-grid details';
    detailGrid.append(
      createSpeakerCardField('組織', makeSheetInput(record, 'organization', {label: '組織', afterInput: refreshIdentity})),
      createSpeakerCardField('部署', makeSheetInput(record, 'department', {label: '部署'})),
      createSpeakerCardField('役職', makeSheetInput(record, 'job_title', {label: '役職', afterInput: refreshIdentity})),
      createSpeakerCardField('守秘同意', makeSheetSelect(record, 'confidentiality_status', consentLabels, {label: '守秘同意'})),
      createSpeakerCardField('タグ', makeSheetInput(record, 'tags', {label: 'タグ', placeholder: '例：顧客, 管理職'}), true),
      createSpeakerCardField('事前アンケート回答', makeAttributesControl(record, '事前アンケート回答'), true),
      createSpeakerCardField('備考', makeSheetInput(record, 'notes', {multiline: true, label: '備考'}), true)
    );
    details.append(summary, detailGrid);

    const footer = document.createElement('footer');
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'sheet-delete';
    remove.textContent = 'この話者を削除';
    remove.addEventListener('click', () => removeSpeakerRecord(record));
    footer.append(remove);

    card.append(header, primary, details, footer);
    speakerRegistryList.append(card);
  });
}

function renderSpeakerRegistry() {
  if (!speakerRegistryBody || !speakerRegistryList) return;
  const visible = visibleSpeakerRegistry();
  if (mobileWizardMedia.matches) {
    speakerRegistryBody.replaceChildren();
    renderSpeakerRegistryCards(visible);
  } else {
    speakerRegistryList.replaceChildren();
    renderSpeakerRegistryTable(visible);
  }
  updateSpeakerRegistryOverview();
  renderSpeakerSurveyAnalysis();
  const count = document.querySelector('#speaker-registry-count');
  if (count) count.textContent = `${visible.length}人を表示（登録 ${speakerRegistry.length}人）`;
}

function downloadUnsavedDraft(kind) {
  if (kind === 'transcript') captureSessionProfile();
  const data = kind === 'transcript'
    ? {schema: 'gurumoji.unsaved-transcript.v1', item_id: currentJobId, base_revision: currentJob?.revision_count, draft: deepCopy(currentJob)}
    : {schema: 'gurumoji.unsaved-speakers.v1', base_revision: speakerRegistryRevision, speakers: deepCopy(speakerRegistry), delete_ids: [...speakerRegistryDeletedIds]};
  const blob = new Blob([JSON.stringify({...data, exported_at: new Date().toISOString()}, null, 2)], {type: 'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `gurumoji-unsaved-${kind}-${Date.now()}.json`;
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function showDraftRecovery(kind) {
  const panel = document.querySelector(kind === 'transcript' ? '#result-draft-recovery' : '#speaker-draft-recovery');
  if (!panel) return;
  panel.hidden = false;
  const count = kind === 'transcript'
    ? (currentJob?.segments || []).filter(segment => JSON.stringify(segment) !== JSON.stringify((currentJobBaseline?.segments || []).find(item => item.id === segment.id))).length
    : speakerRegistry.filter(record => JSON.stringify(record) !== JSON.stringify(speakerRegistryBaseline.find(item => item.id === record.id))).length;
  const deleted = kind === 'transcript' ? (currentJobBaseline?.segments || []).filter(item => !(currentJob?.segments || []).some(segment => segment.id === item.id)).length : speakerRegistryDeletedIds.size;
  panel.querySelector('[data-draft-count]').textContent = `追加・変更 ${count}件 / 削除 ${deleted}件。会話設定も含む未保存内容全体をJSONで退避できます。退避後に再読み込みし、最新の内容と照合してください。自動上書きはしません。`;
  panel.querySelector('button')?.focus();
}
listen(document.querySelector('#export-result-draft'), 'click', () => downloadUnsavedDraft('transcript'));
listen(document.querySelector('#export-speaker-draft'), 'click', () => downloadUnsavedDraft('speakers'));

async function saveSpeakerRegistry() {
  if (speakerRegistrySaveInProgress) return;
  const invalid = speakerRegistry.find(record => (
    !String(record.participant_code || '').trim()
    && !String(record.display_name || '').trim()
    && !String(record.pseudonym || '').trim()
  ));
  if (invalid) {
    setAlert(document.querySelector('#speaker-registry-message'), '氏名、仮名、参加者コードのいずれかを入力してください。', true);
    return;
  }
  const button = speakerRegistrySaveButton;
  const saveGeneration = speakerRegistryMutationGeneration;
  speakerRegistrySaveInProgress = true;
  if (button) button.disabled = true;
  try {
    const response = await apiFetch('/api/speakers', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        registry_revision: speakerRegistryRevision,
        speakers: speakerRegistry,
        delete_ids: [...speakerRegistryDeletedIds]
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) {
      const conflict = response.status === 409
        ? '別の画面で話者管理が更新されています。未保存内容をJSONで退避してから再読み込みしてください。'
        : '話者管理データを保存できませんでした。';
      if (response.status === 409) { speakerSaveConflict = true; showDraftRecovery('speakers'); }
      throw new Error(response.status === 409 ? conflict : (data.error || conflict));
    }
    speakerRegistryRevision = Number(data.registry_revision || speakerRegistryRevision);
    if (speakerRegistryMutationGeneration === saveGeneration) {
      speakerRegistry = data.speakers || [];
      speakerRegistryBaseline = deepCopy(speakerRegistry);
      speakerSaveConflict = false;
      document.querySelector('#speaker-draft-recovery').hidden = true;
      speakerRegistryDeletedIds.clear();
      setSpeakerRegistryDirty(false);
      renderSpeakerRegistry();
      setAlert(document.querySelector('#speaker-registry-message'), `${speakerRegistry.length}人の話者情報を保存しました。`);
      if (currentJob && !resultCard.hidden) renderSpeakerEditor();
    } else {
      setSpeakerRegistryDirty(true, false);
      setAlert(document.querySelector('#speaker-registry-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    speakerRegistrySaveInProgress = false;
    if (button) button.disabled = !speakerRegistryDirty;
  }
}

listen(document.querySelector('#add-speaker-button'), 'click', () => {
  const record = blankSpeakerRecord();
  const search = document.querySelector('#speaker-registry-search');
  const role = document.querySelector('#speaker-registry-role-filter');
  const showInactive = document.querySelector('#speaker-registry-show-inactive');
  if (search) search.value = '';
  if (role) role.value = '';
  if (showInactive) showInactive.checked = true;
  speakerRegistry.unshift(record);
  setSpeakerRegistryDirty();
  renderSpeakerRegistry();
  window.requestAnimationFrame(() => {
    const control = document.querySelector(`[data-speaker-id="${record.id}"][data-speaker-field="participant_code"]`);
    if (control) {
      control.scrollIntoView({behavior: 'smooth', block: 'center'});
      control.focus();
    }
  });
});
listen(speakerRegistrySaveButton, 'click', saveSpeakerRegistry);
listen(document.querySelector('#speaker-registry-search'), 'input', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-role-filter'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-show-inactive'), 'change', renderSpeakerRegistry);
listen(document.querySelector('#speaker-registry-clear-filters'), 'click', () => {
  const search = document.querySelector('#speaker-registry-search');
  const role = document.querySelector('#speaker-registry-role-filter');
  const showInactive = document.querySelector('#speaker-registry-show-inactive');
  if (search) search.value = '';
  if (role) role.value = '';
  if (showInactive) showInactive.checked = true;
  renderSpeakerRegistry();
});
function cancelSpeakerImport() {
  pendingSpeakerImport = null;
  document.querySelector('#speaker-import-preview').hidden = true;
  document.querySelector('#speaker-csv-input').value = '';
}
listen(document.querySelector('#cancel-speaker-import'), 'click', cancelSpeakerImport);
listen(document.querySelector('#apply-speaker-import'), 'click', () => {
  if (!pendingSpeakerImport) return;
  if (speakerRegistryMutationGeneration !== pendingSpeakerImport.generation || speakerRegistryRevision !== pendingSpeakerImport.revision) {
    setAlert(document.querySelector('#speaker-registry-message'), 'プレビュー後に編集されました。現在の変更を保存してからCSVを読み直してください。', true);
    cancelSpeakerImport(); return;
  }
  speakerRegistry = pendingSpeakerImport.speakers;
  setSpeakerRegistryDirty(); renderSpeakerRegistry(); cancelSpeakerImport();
  setAlert(document.querySelector('#speaker-registry-message'), 'CSVを未保存の編集内容に反映しました。内容を確認して「変更を保存」を押してください。');
  speakerRegistrySaveButton?.focus();
});
listen(document.querySelector('#import-speakers-button'), 'click', () => {
  if (speakerRegistrySaveInProgress) return;
  if (speakerRegistryDirty) {
    setAlert(document.querySelector('#speaker-registry-message'), '先に現在の編集を保存してください。保存できない場合は未保存内容を退避できます。CSVで編集を上書きしません。', true);
    showDraftRecovery('speakers'); return;
  }
  document.querySelector('#speaker-csv-input')?.click();
});
listen(document.querySelector('#speaker-csv-input'), 'change', async event => {
  const file = event.target.files && event.target.files[0];
  if (!file || speakerRegistrySaveInProgress) return;
  if (speakerRegistryDirty) {
    setAlert(document.querySelector('#speaker-registry-message'), '現在の編集を先に保存してください。CSV取込では未保存編集を置き換えません。', true);
    event.target.value = ''; return;
  }
  cancelSpeakerImport();
  const body = new FormData();
  body.append('csv_file', file);
  body.append('registry_revision', String(speakerRegistryRevision));
  body.append('preview', '1');
  const generation = speakerRegistryMutationGeneration;
  speakerRegistrySaveInProgress = true;
  const importButton = document.querySelector('#import-speakers-button');
  importButton.disabled = true;
  setAlert(document.querySelector('#speaker-registry-message'), 'CSVを検証しています。まだ保存していません');
  try {
    const response = await apiFetch('/api/speakers/import', {method: 'POST', body});
    const data = await readJsonResponse(response);
    if (!response.ok) {
      if (response.status === 409) showDraftRecovery('speakers');
      throw new Error(response.status === 409 ? '話者管理が更新されています。編集を退避し、再読み込みしてからCSVを読み込んでください。' : (data.error || 'CSVを読み込めませんでした。'));
    }
    if (generation !== speakerRegistryMutationGeneration) throw new Error('CSV確認中に編集されました。編集を保存してからCSVを読み直してください。');
    if (!data.preview) throw new Error('このサーバーはCSVプレビューに対応していません。画面を再読み込みしてください。');
    pendingSpeakerImport = {speakers: data.speakers || [], revision: data.registry_revision, generation};
    const summary = data.summary || {};
    document.querySelector('#speaker-import-summary').textContent = `${file.name}: ${data.imported_count}行 / 追加 ${summary.added || 0}人 / 更新 ${summary.updated || 0}人。まだ保存していません`;
    const columns = document.querySelector('#speaker-import-columns');
    columns.replaceChildren();
    (summary.columns || []).forEach(column => {
      const item = document.createElement('li');
      item.textContent = `${column.column} → ${column.field === 'attributes' ? '追加属性（事前アンケート回答）' : column.field === 'ignored' ? '取込対象外' : column.field}`;
      columns.append(item);
    });
    document.querySelector('#speaker-import-preview').hidden = false;
    setAlert(document.querySelector('#speaker-registry-message'), '列対応と追加・更新件数を確認してください。キャンセルしても保存状態は変わりません。');
    document.querySelector('#apply-speaker-import').focus();
  } catch (error) {
    setAlert(document.querySelector('#speaker-registry-message'), error.message, true);
  } finally {
    speakerRegistrySaveInProgress = false;
    importButton.disabled = false;
    if (speakerRegistrySaveButton) speakerRegistrySaveButton.disabled = !speakerRegistryDirty;
    event.target.value = '';
  }
});

const roleFilter = document.querySelector('#speaker-registry-role-filter');
if (roleFilter) {
  Object.entries(speakerRoleLabels).forEach(([value, label]) => roleFilter.add(new Option(label, value)));
}

mobileWizardMedia.addEventListener('change', () => {
  if (speakerRegistryLoaded) renderSpeakerRegistry();
  setLibraryFiltersOpen(false);
});

listen(customVocabulary, 'input', () => {
  customVocabularyTouched = true;
  customVocabularyMutationGeneration += 1;
  scheduleCustomVocabularySave();
  updateCreateSummary();
});

listen(customVocabulary, 'blur', () => {
  if (customVocabularyTouched) scheduleCustomVocabularySave({immediate: true});
});

listen(sourcePath, 'input', () => {
  setAlert(pathError, '');
  const value = sourcePath.value.trim();
  if (value && inputFile) inputFile.value = '';
  pathDetail.textContent = value
    ? `${value.split(/[\\/]/).pop()} — このパスを直接処理します`
    : 'ファイルが選択されていません';
  scheduleSourceThumbnail(value);
  updateCreateSummary();
});

listen(browsePathButton, 'click', async () => {
  setAlert(pathError, '');
  if (!browsePathButton) return;
  if (browserFilePickerOnly || isMobileWizard()) {
    if (inputFile) inputFile.click();
    return;
  }
  browsePathButton.disabled = true;
  browsePathButton.textContent = '選択画面を開いています…';
  try {
    const response = await apiFetch('/api/select-input', {method: 'POST', cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error([data.error, data.hint].filter(Boolean).join('\n'));
    if (data.cancelled) return;
    if (inputFile) inputFile.value = '';
    sourcePath.value = data.path || '';
    pathDetail.textContent = `${data.name || data.path} / ${formatBytes(Number(data.size))} — アップロードせず、このパスを直接処理します`;
    showSourceThumbnail(data.path || '', data.name || '');
    updateCreateSummary();
  } catch (error) {
    setAlert(pathError, error.message || 'ファイル選択に失敗しました。', true);
  } finally {
    browsePathButton.disabled = false;
    updateBrowseButtonLabel();
  }
});

listen(fileDropZone, 'keydown', event => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  if (!jobRunning && browsePathButton) browsePathButton.click();
});

function handleInputFileSelection() {
  setAlert(pathError, '');
  const file = inputFile.files && inputFile.files[0];
  if (file) {
    if (!/\.(mp4|m4v|mov|mkv|wav|mp3|m4a|flac)$/i.test(file.name)) {
      inputFile.value = '';
      sourcePath.value = '';
      hideSourcePreview();
      pathDetail.textContent = 'ファイルが選択されていません';
      setAlert(pathError, '対応している動画・音声ファイルを選択してください。', true);
      updateCreateSummary();
      return;
    }
    sourcePath.value = '';
    pathDetail.textContent = browserFilePickerOnly
      ? `${file.name} / ${formatBytes(file.size)} — Colabへ一時アップロードして処理します`
      : `${file.name} / ${formatBytes(file.size)} — Gurumoji実行環境へ一時コピーして処理します`;
    hideSourcePreview();
  } else if (!sourcePath.value.trim()) {
    pathDetail.textContent = 'ファイルが選択されていません';
  }
  updateCreateSummary();
}

listen(inputFile, 'change', handleInputFileSelection);

['dragenter', 'dragover'].forEach(eventName => {
  listen(fileDropZone, eventName, event => {
    event.preventDefault();
    if (!jobRunning) fileDropZone.classList.add('is-dragging');
  });
});
['dragleave', 'drop'].forEach(eventName => {
  listen(fileDropZone, eventName, event => {
    event.preventDefault();
    fileDropZone.classList.remove('is-dragging');
  });
});
listen(fileDropZone, 'drop', event => {
  if (jobRunning || !inputFile) return;
  const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
  if (!file) return;
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputFile.files = transfer.files;
    handleInputFileSelection();
  } catch (error) {
    setAlert(pathError, 'ドラッグ＆ドロップを利用できません。［ファイルを選択］から指定してください。', true);
  }
});

function setHardwareLight(element, available, availableText, unavailableText, title = '') {
  if (!element) return;
  element.classList.remove('checking', 'available', 'unavailable');
  element.classList.add(available ? 'available' : 'unavailable');
  element.textContent = available ? availableText : unavailableText;
  element.title = title;
}

function setHardwareLights(kind, available, availableText, unavailableText, title = '') {
  document.querySelectorAll(`[data-hardware="${kind}"]`).forEach(element => {
    setHardwareLight(element, available, availableText, unavailableText, title);
  });
  document.querySelectorAll(`[data-device-dot="${kind}"]`).forEach(element => {
    element.classList.remove('checking', 'available', 'unavailable');
    element.classList.add(available ? 'available' : 'unavailable');
    element.title = title;
  });
}

function applyMachineProfile(machine, {reset = false} = {}) {
  if (!machine) return;
  lastMachineProfile = machine;
  if (reset) manuallySelectedMachineFields.clear();
  const changes = [];
  const cpu = machine.cpu || {};
  const gpu = machine.gpu || {};
  const recommended = machine.recommended || {};
  const summary = document.querySelector('#machine-summary');
  const recommendation = document.querySelector('#machine-recommendation');
  const modelSelect = document.querySelector('#model-name');
  const transcriptionDevice = document.querySelector('#transcription-device');
  const diarizationDevice = document.querySelector('#diarization-device');

  setHardwareLights(
    'cpu',
    Boolean(cpu.available),
    'CPU 利用可',
    'CPU 利用不可',
    `${cpu.name || 'CPU'} / ${cpu.logical_threads || '?'} threads`
  );
  setHardwareLights(
    'gpu',
    Boolean(gpu.cuda_available),
    'GPU 利用可',
    'GPU 利用不可',
    gpu.cuda_available
      ? `${gpu.name || 'CUDA GPU'} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB`
      : (gpu.reason || 'CUDAを利用できません')
  );

  const cpuParts = [
    cpu.name || 'CPU',
    `${cpu.logical_threads || '?'} threads`,
  ];
  if (Number(machine.memory_gib) > 0) cpuParts.push(`RAM ${Number(machine.memory_gib).toFixed(1)} GB`);
  const gpuText = gpu.cuda_available
    ? `${gpu.name} / VRAM ${Number(gpu.vram_gib || 0).toFixed(1)} GB / CUDA ${gpu.cuda_version || '?'} / CC ${gpu.capability || '?'}`
    : (gpu.reason || 'CUDA GPUは利用できません');
  if (summary) summary.textContent = `${cpuParts.join(' / ')}　｜　${gpuText}`;

  [transcriptionDevice, diarizationDevice].forEach(select => {
    if (!select) return;
    const cudaOption = select.querySelector('option[value="cuda"]');
    if (cudaOption) cudaOption.disabled = !gpu.cuda_available;
    if (!gpu.cuda_available && select.value === 'cuda') {
      select.value = 'cpu';
      changes.push('選択したGPUを利用できないためCPUに変更しました');
    }
  });

  if (modelSelect && !manuallySelectedMachineFields.has(modelSelect.id) && [...modelSelect.options].some(option => option.value === recommended.model_name)) {
    modelSelect.value = recommended.model_name;
  }
  if (transcriptionDevice && !manuallySelectedMachineFields.has(transcriptionDevice.id) && [...transcriptionDevice.options].some(option => (
    option.value === recommended.device && !option.disabled
  ))) {
    transcriptionDevice.value = recommended.device;
  }
  if (diarizationDevice && !manuallySelectedMachineFields.has(diarizationDevice.id) && [...diarizationDevice.options].some(option => (
    option.value === recommended.diarization_device && !option.disabled
  ))) {
    diarizationDevice.value = recommended.diarization_device;
  }

  if (recommendation) {
    const deviceLabel = recommended.device === 'cuda' ? 'GPU' : 'CPU';
    const diarizationLabel = recommended.diarization_device === 'cuda' ? 'GPU' : 'CPU';
    recommendation.textContent = recommended.model_name
      ? `推奨設定（手動選択を保持）: ${recommended.model_name} / 文字起こし ${deviceLabel} / 話者分離 ${diarizationLabel}。${recommended.reason || ''}`
      : '';
  }
  setAlert(document.querySelector('#machine-selection-message'), [...new Set(changes)].join('。'), Boolean(changes.length));
  updateCreateSummary();
}

['model-name', 'transcription-device', 'diarization-device'].forEach(id => {
  listen(document.getElementById(id), 'change', () => manuallySelectedMachineFields.add(id));
});
listen(document.querySelector('#machine-reset-button'), 'click', () => applyMachineProfile(lastMachineProfile, {reset: true}));
listen(document.querySelector('#setup-open-connections'), 'click', () => document.querySelector('#connection-button')?.click());
listen(document.querySelector('#setup-recheck'), 'click', loadConfig);
listen(document.querySelector('#model-readiness-ack'), 'change', updateCreateSummary);

async function loadConfig() {
  const message = document.querySelector('#token-message');
  if (!message) return;
  configLoadState = 'loading';
  updateCreateSummary();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await apiFetch('/api/config', {cache: 'no-store', signal: controller.signal});
    const data = await readJsonResponse(response);
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    tokenConfigSnapshot = data && typeof data === 'object' ? data : {};
    configLoadState = 'loaded';
    applyMachineProfile(data.machine);
    applyObsidianWatcherStatus(data.obsidian_watcher);
    const runtime = data.runtime || {};
    browserFilePickerOnly = Boolean(runtime.browser_upload);
    if (browsePathButton) {
      browsePathButton.dataset.pickerMode = browserFilePickerOnly ? 'browser' : 'native';
      updateBrowseButtonLabel();
    }
    if (!response.ok || !data.ok) throw new Error(data.error || '設定を取得できません');
    const recognized = [];
    const localLlmShortLabel = String(data.local_llm_short_label || 'LM Studio');
    [
      ['hf', 'huggingface', 'Hugging Face'],
      ['openai', 'openai', 'OpenAI'],
      ['google', 'google', 'Google'],
      ['typesafe', 'typesafe', 'TypeSafe Jev'],
      ['lmstudio', 'lmstudio', localLlmShortLabel]
    ].forEach(([id, key, label]) => {
      // The hero pills are hidden on phones; the mobile header repeats them (UX-10).
      document.querySelectorAll(`#status-${id}, [data-status-provider="${id}"]`).forEach(pill => {
        pill.classList.remove('loading', 'ready', 'missing');
        pill.classList.add(data[key] ? 'ready' : 'missing');
        pill.textContent = data[key] ? `${label} ✓` : label;
        const lmStudioStatus = key === 'lmstudio' && data.lmstudio_status && typeof data.lmstudio_status === 'object'
          ? data.lmstudio_status : null;
        pill.title = lmStudioStatus
          ? String(lmStudioStatus.message || '')
          : (data[key] ? '設定済み' : '未設定');
        if (pill.dataset.modelProvider) {
          const currentModel = String(data[`${key}_model`] || '').trim();
          pill.dataset.currentModel = currentModel;
          pill.title = key === 'lmstudio'
            ? `${lmStudioStatus && lmStudioStatus.message || 'ローカルLLMの状態を確認できません。'}${currentModel ? ` 現在: ${currentModel}` : ''}`
            : data[key]
            ? `クリックしてモデルを変更（現在: ${currentModel || 'tokens.json の設定'}）`
            : `${label} APIキーがtokens.jsonに設定されていません`;
        }
      });
      document.querySelectorAll(`[data-provider-model="${key}"]`).forEach(element => {
        element.textContent = String(data[`${key}_model`] || '').trim() || '未設定';
      });
      document.querySelectorAll(`[data-connection-dot="${id}"]`).forEach(dot => {
        dot.classList.toggle('ready', Boolean(data[key]));
        dot.classList.toggle('missing', !data[key]);
      });
      if (data[key]) recognized.push(label);
    });
    const outputDir = document.querySelector('#output-dir');
    if (outputDir) outputDir.placeholder = `${data.default_output_dir}（実行ごとにサブフォルダーを作成）`;
    message.textContent = recognized.length
      ? `利用可能: ${recognized.join(' / ')}。発光している項目を使用できます。`
      : 'トークンを認識できません。tokens.json を確認してください。';
    applyLmStudioDefaults(data);
    syncAiFields();
    updateCreateSummary();
  } catch (error) {
    configLoadState = 'error';
    message.textContent = error.name === 'AbortError'
      ? '設定確認がタイムアウトしました。アプリを再起動して http://127.0.0.1:7860 を開き直してください。'
      : error.message;
    message.style.color = '#913733';
  } finally {
    window.clearTimeout(timeoutId);
    updateCreateSummary();
  }
}

function applyObsidianWatcherStatus(watcher) {
  // OBS-09: a watcher that stopped at startup must not look like an idle one.
  if (!watcher || typeof watcher !== 'object' || !watcher.state) return;
  const failed = ['failed', 'polling_failed'].includes(watcher.state);
  // OBS-10: a parent folder opened as a Vault mixes the app's notes into it.
  const warnings = Array.isArray(watcher.warnings) ? watcher.warnings.filter(Boolean) : [];
  document.querySelectorAll('[data-obsidian-watcher-pill]').forEach(pill => {
    pill.classList.remove('loading', 'ready', 'missing');
    pill.classList.add(watcher.state === 'running' && !warnings.length ? 'ready' : failed || warnings.length ? 'missing' : 'loading');
    pill.textContent = watcher.state === 'running' ? 'Obsidian監視 ✓' : 'Obsidian監視';
  });
  document.querySelectorAll('[data-obsidian-watcher-detail]').forEach(detail => {
    detail.textContent = [watcher.message, watcher.detail, ...warnings.map(text => `注意: ${text}`)].filter(Boolean).join(' ');
  });
}

// DATA-03: one consistent copy of what cannot be recreated.
listen(document.querySelector('#create-backup-button'), 'click', async () => {
  const button = document.querySelector('#create-backup-button');
  const message = document.querySelector('#backup-message');
  const includeMedia = document.querySelector('#backup-include-media');
  button.disabled = true;
  setAlert(message, 'バックアップを作成しています。完了まで保存操作は待機します…');
  try {
    const response = await apiFetch('/api/system/backup', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({include_media: Boolean(includeMedia && includeMedia.checked)})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'バックアップを作成できませんでした。');
    setAlert(message, `作成しました: ${data.path}（${data.file_count}ファイル）。含めていないもの: ${(data.excluded || []).join('、')}`);
  } catch (error) {
    setAlert(message, error.message, true);
  } finally {
    button.disabled = false;
  }
});

function applyLmStudioDefaults(config) {
  // A ready, explicitly selected local model is an opt-in.  Make the
  // transcription form ready to use it without requiring three more clicks.
  // Do not choose the local server when it is offline or a model was not
  // selected yet: either state would make the default form fail at submission.
  if (!aiProvider || aiProviderManuallySelected || aiProvider.value !== 'none' || !config || !config.lmstudio || !String(config.lmstudio_model || '').trim()) return;
  aiProvider.value = 'lmstudio';
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
}

function clearSystemActivityPolling() {
  if (systemActivityTimer !== null) window.clearTimeout(systemActivityTimer);
  systemActivityTimer = null;
  if (systemActivityController) systemActivityController.abort();
  systemActivityController = null;
}

function formatActivityRate(mebibytesPerSecond) {
  const value = Math.max(0, Number(mebibytesPerSecond) || 0);
  if (value >= 1) return `${value.toFixed(value >= 10 ? 0 : 1)} MB/s`;
  return `${Math.round(value * 1024)} KB/s`;
}

function setResourceMetric(name, payload, detail) {
  const available = Boolean(payload && payload.available);
  const percent = Math.max(0, Math.min(100, Number(payload && payload.utilization_percent) || 0));
  const value = document.querySelector(`#monitor-${name}-value`);
  const bar = document.querySelector(`#monitor-${name}-bar`);
  const detailElement = document.querySelector(`#monitor-${name}-detail`);
  const card = value ? value.closest('.resource-metric') : null;
  if (value) {
    const displayedPercent = name === 'cpu' ? percent.toFixed(1) : Math.round(percent);
    value.textContent = available ? `${displayedPercent}%` : '--%';
  }
  if (bar) bar.style.width = available ? `${percent}%` : '0%';
  if (detailElement) detailElement.textContent = available ? detail : '利用できません';
  if (card) card.classList.toggle('is-unavailable', !available);
}

function renderSystemActivity(activity) {
  document.querySelectorAll('.resource-metric').forEach(card => card.classList.remove('is-stale'));
  const cpu = activity && activity.cpu ? activity.cpu : {};
  const memory = activity && activity.memory ? activity.memory : {};
  const gpu = activity && activity.gpu ? activity.gpu : {};
  const disk = activity && activity.disk ? activity.disk : {};
  setResourceMetric('cpu', cpu, 'システム全体の使用率');
  setResourceMetric(
    'memory',
    memory,
    `${Number(memory.used_gib || 0).toFixed(1)} / ${Number(memory.total_gib || 0).toFixed(1)} GB`
  );
  setResourceMetric(
    'gpu',
    gpu,
    gpu.available
      ? `VRAM ${Number(gpu.memory_used_gib || 0).toFixed(1)} / ${Number(gpu.memory_total_gib || 0).toFixed(1)} GB (${Math.round(Number(gpu.memory_percent || 0))}%)`
      : ''
  );
  const readLight = document.querySelector('#monitor-read-light');
  const writeLight = document.querySelector('#monitor-write-light');
  const readRate = document.querySelector('#monitor-read-rate');
  const writeRate = document.querySelector('#monitor-write-rate');
  if (readLight) readLight.classList.toggle('is-active', Boolean(disk.available && disk.read_active));
  if (writeLight) writeLight.classList.toggle('is-active', Boolean(disk.available && disk.write_active));
  if (readRate) readRate.textContent = disk.available ? formatActivityRate(disk.read_mib_per_second) : '--';
  if (writeRate) writeRate.textContent = disk.available ? formatActivityRate(disk.write_mib_per_second) : '--';
}

function scheduleSystemActivityPolling() {
  if (!jobRunning || systemActivityTimer !== null || systemActivityController) return;
  systemActivityTimer = window.setTimeout(() => {
    systemActivityTimer = null;
    pollSystemActivity();
  }, systemActivityDelayMs);
}

async function pollSystemActivity() {
  if (!jobRunning || !progressCard || progressCard.hidden || systemActivityController) return;
  const controller = new AbortController();
  systemActivityController = controller;
  try {
    const response = await apiFetch('/api/system/activity', {cache: 'no-store', signal: controller.signal});
    const activity = await readJsonResponse(response);
    if (!response.ok) throw new Error(activity.error || 'システム使用状況を取得できませんでした。');
    if (jobRunning) renderSystemActivity(activity);
  } catch (error) {
    if (error.name !== 'AbortError') {
      document.querySelectorAll('.resource-metric').forEach(card => card.classList.add('is-stale'));
    }
  } finally {
    if (systemActivityController === controller) systemActivityController = null;
    scheduleSystemActivityPolling();
  }
}

function startSystemActivityPolling() {
  if (!jobRunning || !progressCard || progressCard.hidden) return;
  if (systemActivityTimer === null && !systemActivityController) pollSystemActivity();
}

function setRunning(running) {
  if (!form) return;
  jobRunning = running;
  if (running) startSystemActivityPolling();
  else clearSystemActivityPolling();
  [...form.elements].forEach(element => {
    element.disabled = running || element.dataset.alwaysDisabled === 'true';
  });
  if (fixedSpeakerCountInput) fixedSpeakerCountInput.disabled = running || !isSpeakerCountFixed();
  if (cancelButton) cancelButton.disabled = !running;
  syncQuietFields();
  syncEmotionFields();
  syncAiFields();
  updateCreateSummary();
  syncCreateViewState();
}

function syncQuietFields() {
  const controlsDisabled = (boostQuietSpeech && boostQuietSpeech.disabled) || (triplePass && triplePass.disabled);
  const enabled = ((boostQuietSpeech && boostQuietSpeech.checked) || (triplePass && triplePass.checked)) && !controlsDisabled;
  [vadOnset, vadOffset].forEach(input => { if (input) input.disabled = !enabled; });
}

function syncEmotionFields() {
  if (emotionModel) emotionModel.disabled = !emotionAnalysis || emotionAnalysis.disabled || !emotionAnalysis.checked;
}

function syncAiFields() {
  if (!aiProvider) return;
  const providerDisabled = aiProvider.disabled;
  const disabled = providerDisabled || aiProvider.value === 'none';
  aiOptionInputs.forEach(input => {
    if (aiProvider.value === 'none') input.checked = false;
    input.disabled = disabled;
    const row = input.closest('.check-row');
    if (row) row.classList.toggle('disabled', disabled);
  });
  if (jevCompare) {
    const jevDisabled = disabled || !tokenConfigSnapshot.typesafe;
    if (jevDisabled) jevCompare.checked = false;
    jevCompare.disabled = jevDisabled;
    const row = jevCompare.closest('.check-row');
    if (row) row.classList.toggle('disabled', jevDisabled);
    if (jevConfigStatus) {
      jevConfigStatus.textContent = tokenConfigSnapshot.typesafe
        ? `TypeSafe ${tokenConfigSnapshot.typesafe_model || 'jev-latest'} を使用できます。`
        : 'おすすめのJev判定／Jev比較には tokens.json の typesafe_api_key が必要です。';
    }
  }
  if (typeof syncAiEffortSettings === 'function') syncAiEffortSettings();
}

function selectedTranscriptFinishingMode() {
  const selected = transcriptFinishingModeInputs.find(input => input.checked);
  return selected ? selected.value : 'recommended';
}

// Remember optional choices per finishing mode. A mode's mandated execution
// is modeled separately by aiEffortStagePlan, not by rewriting another mode's
// preferences. This is transient form state, never a second effort store.
const transcriptFinishingPreferences = new Map();
let lastTranscriptFinishingMode = selectedTranscriptFinishingMode();

function applyTranscriptFinishingModeChange() {
  const mode = selectedTranscriptFinishingMode();
  if (mode === lastTranscriptFinishingMode) return;
  const controls = [cleanTranscript, detectNames, createOutline, jevCompare, finishInObsidian];
  transcriptFinishingPreferences.set(lastTranscriptFinishingMode, controls.map(input => Boolean(input?.checked)));
  const saved = transcriptFinishingPreferences.get(mode);
  applyTranscriptFinishingPreset();
  if (saved) controls.forEach((input, index) => { if (input) input.checked = saved[index]; });
  lastTranscriptFinishingMode = mode;
}

function applyTranscriptFinishingPreset() {
  const mode = selectedTranscriptFinishingMode();
  const hasAi = Boolean(aiProvider && aiProvider.value !== 'none');
  if (cleanTranscript) cleanTranscript.checked = mode === 'advanced' && hasAi;
  if (detectNames) detectNames.checked = mode !== 'off' && hasAi;
  if (createOutline) createOutline.checked = mode === 'advanced' && hasAi;
  // An additional external destination must be an explicit choice.
  if (jevCompare && (mode !== 'advanced' || !hasAi)) jevCompare.checked = false;
  if (finishInObsidian && mode !== 'recommended') finishInObsidian.checked = false;
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
  if (finishingModeHint) {
    finishingModeHint.textContent = {
      recommended: 'AI仕上げを使う場合は、必要な箇所だけ読みやすく整えます。Obsidianに保存する場合は、あとで仕上げられます。',
      advanced: '文章全体を見直します。話者の確認や比較など、追加の処理も選べます。',
      off: '文章は変更せず、認識結果をそのまま残します。'
    }[mode] || '';
  }
}

function selectDefaultAiOptions() {
  if (!aiProvider) return;
  applyTranscriptFinishingPreset();
  syncAiFields();
  updateCreateSummary();
}

conversationModeInputs.forEach(input => listen(input, 'change', () => {
  if (input.checked) applyConversationMode(input.value);
}));
conversationModeFields.forEach(field => {
  ['input', 'change'].forEach(eventName => listen(field.input, eventName, () => manuallyEditedModeFields.add(field.key)));
});
listen(speakerCountFixButton, 'click', () => setSpeakerCountFixed(!isSpeakerCountFixed()));
listen(fixedSpeakerCountInput, 'input', syncFixedSpeakerCount);
listen(conversationModeResetButton, 'click', () => {
  if (isSpeakerCountFixed()) setSpeakerCountFixed(false, {restoreRange: false});
  manuallyEditedModeFields.clear();
  applyConversationMode();
});
listen(boostQuietSpeech, 'change', syncQuietFields);
listen(triplePass, 'change', () => {
  syncQuietFields();
  updateCreateSummary();
});
listen(emotionAnalysis, 'change', () => {
  syncEmotionFields();
  updateCreateSummary();
});
listen(aiProvider, 'change', () => {
  aiProviderManuallySelected = true;
  selectDefaultAiOptions();
});
function syncFinishingMode() {
  const mode = selectedTranscriptFinishingMode();
  document.querySelectorAll('[data-advanced-finishing-only]').forEach(row => {
    row.hidden = mode !== 'advanced';
  });
  document.querySelectorAll('[data-speaker-finishing-option]').forEach(row => {
    row.hidden = mode === 'off';
  });
}
listen(finishInObsidian, 'change', () => {
  syncFinishingMode();
  updateCreateSummary();
});
applyTranscriptFinishingPreset();
syncFinishingMode();
transcriptFinishingModeInputs.forEach(input => listen(input, 'change', () => {
  applyTranscriptFinishingModeChange();
  syncAiFields();
  updateCreateSummary();
}));
[modelName, languageSelect, audioPreprocess, writeSrt, burnSubtitledVideo].forEach(input => {
  listen(input, 'change', updateCreateSummary);
});
listen(form, 'change', event => {
  if (['ai_effort_choice_cleanup', 'ai_effort_notation'].includes(event.target.name)) window.queueMicrotask(updateCreateSummary);
});
aiOptionInputs.forEach(input => listen(input, 'change', updateCreateSummary));
listen(transcriptionBackend, 'change', () => {
  syncTranscriptionBackend();
  updateCreateSummary();
});
listen(jevCompare, 'change', () => {
  if (jevCompare.checked && cleanTranscript) cleanTranscript.checked = true;
  updateCreateSummary();
});
applyConversationMode();
syncEmotionFields();
syncAiFields();
syncTranscriptionBackend();
updateCreateSummary();

listen(mobileStepBack, 'click', () => setMobileStep(currentMobileStep - 1));
listen(mobileStepNext, 'click', () => setMobileStep(currentMobileStep + 1, {validateCurrent: true}));
document.querySelectorAll('[data-flow-jump]').forEach(button => {
  listen(button, 'click', () => jumpToFlowStep(Number(button.dataset.flowJump)));
});
document.querySelectorAll('[data-open-panel]').forEach(button => {
  listen(button, 'click', () => openSettingsPanel(button.dataset.openPanel));
});
[document.querySelector('#transcription-device'), document.querySelector('#diarization-device'), minSpeakersInput, maxSpeakersInput, boostQuietSpeech].forEach(input => {
  listen(input, 'change', updateCreateSummary);
});
mobileWizardMedia.addEventListener('change', () => {
  updateBrowseButtonLabel();
  renderMobileWizard();
});

if (form) {
  form.addEventListener('invalid', event => {
    const panel = event.target.closest('[data-settings-panel]');
    if (panel) panel.open = true;
    if (!isMobileWizard()) return;
    event.preventDefault();
    const section = event.target.closest('[data-flow-section]');
    if (section) currentMobileStep = Number(section.dataset.flowSection) || currentMobileStep;
    renderMobileWizard();
    setAlert(formError, '入力内容を確認してください。', true);
    window.setTimeout(() => event.target.focus(), 80);
  }, true);
}

function jobFromPayload(payload) {
  if (!payload || typeof payload !== 'object') return null;
  if (payload.id && payload.status) return payload;
  for (const key of ['job', 'active_job', 'activeJob']) {
    const job = payload[key];
    if (job && typeof job === 'object' && job.id && job.status) return job;
  }
  return null;
}

function clearPollTimer() {
  if (pollTimer !== null) window.clearTimeout(pollTimer);
  pollTimer = null;
}

function schedulePoll(delay = pollBaseDelayMs) {
  clearPollTimer();
  if (!activeJobId || !jobRunning) return;
  pollTimer = window.setTimeout(() => {
    pollTimer = null;
    pollJob();
  }, delay);
}

async function fetchActiveJob() {
  const response = await apiFetch('/api/jobs/active', {cache: 'no-store'});
  if (response.status === 204 || response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '実行中ジョブを確認できませんでした。');
  return jobFromPayload(payload);
}

async function fetchPersistedJob(jobId) {
  if (!jobId) return null;
  const response = await apiFetch(`/api/library/${encodeURIComponent(jobId)}`, {cache: 'no-store'});
  if (response.status === 404) return null;
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(payload.error || '保存済み結果を確認できませんでした。');
  return jobFromPayload(payload);
}

function resumeJob(job, {scroll = false} = {}) {
  if (!job || !job.id) return false;
  const cancellable = ['queued', 'running'].includes(job.status);
  const active = cancellable || ['admitting', 'committing'].includes(job.status);
  activeJobId = String(job.id);
  storePendingSubmissionId('');
  clearPollTimer();
  renderProgress(job);
  showProgressCard({scroll});
  if (active) {
    storeActiveJobId(activeJobId);
    setRunning(true);
    if (cancelButton) cancelButton.disabled = !cancellable;
    schedulePoll();
    return true;
  }
  storeActiveJobId('');
  activeJobId = null;
  setRunning(false);
  if (cancelButton) cancelButton.disabled = true;
  if (job.status === 'completed') {
    // Open the result only while the progress screen is on view. Elsewhere the
    // header chip offers it, so a record being edited is never replaced (UX-16).
    if (createView && !createView.hidden) {
      completedJob = null;
      renderResult(job);
    } else {
      completedJob = job;
      updateJobChip(job);
    }
  }
  return true;
}

async function restoreActiveJob() {
  const restoreGeneration = ++jobFlowGeneration;
  setRunning(true);
  if (cancelButton) cancelButton.disabled = true;
  const storedId = storedActiveJobId();
  if (storedId) {
    try {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(storedId)}`, {cache: 'no-store'});
      const payload = await readJsonResponse(response);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (response.ok) {
        const job = jobFromPayload(payload);
        if (job) {
          pollFailureCount = 0;
          resumeJob(job);
          return;
        }
      } else if (response.status !== 404) {
        throw new Error(payload.error || '保存したジョブへ再接続できませんでした。');
      }
      const persistedJob = await fetchPersistedJob(storedId);
      if (restoreGeneration !== jobFlowGeneration) return;
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      storeActiveJobId('');
    } catch (_) {
      if (restoreGeneration !== jobFlowGeneration) return;
      activeJobId = storedId;
      storeActiveJobId(storedId);
      setRunning(true);
      showProgressCard();
      const message = document.querySelector('#progress-message');
      if (message) message.textContent = '実行中ジョブへ再接続しています…';
      schedulePoll();
      return;
    }
  }
  const pendingSubmissionId = storedPendingSubmissionId();
  if (pendingSubmissionId) {
    if (pendingSubmissionRetryAllowed(pendingSubmissionId)) {
      setRunning(false);
      setAlert(
        formError,
        '前回の送信は未受付と確認されました。同じ送信IDで安全に再送できます。必要ならファイルを選び直して［文字起こしを開始］を押してください。',
        true
      );
      return;
    }
    setRunning(true);
    showProgressCard();
    const message = document.querySelector('#progress-message');
    if (message) message.textContent = '送信中だったジョブの受付状況を確認しています…';
    await recoverSubmittedJob(
      '送信中にページが再読み込みされました。',
      pendingSubmissionId,
      0,
      restoreGeneration
    );
    return;
  }
  try {
    const activeJob = await fetchActiveJob();
    if (restoreGeneration !== jobFlowGeneration) return;
    if (activeJob) {
      pollFailureCount = 0;
      resumeJob(activeJob);
      return;
    }
  } catch (_) {
    // Older backends may not expose /api/jobs/active yet. Normal startup continues.
  }
  if (restoreGeneration === jobFlowGeneration) {
    activeJobId = null;
    setRunning(false);
    if (cancelButton) cancelButton.disabled = true;
  }
}

async function recoverSubmittedJob(
  errorMessage,
  submissionId,
  attempt = 0,
  recoveryGeneration = jobFlowGeneration,
  absenceConfirmed = false
) {
  if (recoveryGeneration !== jobFlowGeneration) return;
  let confirmedAbsentThisAttempt = false;
  try {
    let recoveredJob = null;
    let exactAbsent = !submissionId;
    let persistedAbsent = !submissionId;
    if (submissionId) {
      const response = await apiFetch(`/api/jobs/${encodeURIComponent(submissionId)}`, {cache: 'no-store'});
      if (response.ok) recoveredJob = jobFromPayload(await readJsonResponse(response));
      else if (response.status !== 404) {
        const payload = await readJsonResponse(response);
        throw new Error(payload.error || '送信したジョブを確認できませんでした。');
      } else {
        exactAbsent = true;
      }
      if (!recoveredJob) {
        recoveredJob = await fetchPersistedJob(submissionId);
        persistedAbsent = !recoveredJob;
      }
    }
    let activeAbsent = false;
    if (!recoveredJob) {
      recoveredJob = await fetchActiveJob();
      activeAbsent = !recoveredJob;
    }
    confirmedAbsentThisAttempt = exactAbsent && persistedAbsent && activeAbsent;
    if (recoveryGeneration !== jobFlowGeneration) return;
    if (recoveredJob) {
      pollFailureCount = 0;
      resumeJob(recoveredJob, {scroll: true});
      setAlert(formError, '送信結果を再確認し、文字起こしジョブへ接続しました。', true);
      return;
    }
  } catch (_) {
    // A transient read failure is handled by the same bounded retry as a 404/204.
  }
  if (recoveryGeneration !== jobFlowGeneration) return;
  const confirmedAbsent = absenceConfirmed || confirmedAbsentThisAttempt;
  if (attempt + 1 >= submitRecoveryMaxAttempts) {
    storeActiveJobId('');
    activeJobId = null;
    setRunning(false);
    if (progressCard) progressCard.hidden = true;
    if (confirmedAbsent) markPendingSubmissionRetryable(submissionId);
    setAlert(
      formError,
      confirmedAbsent
        ? `${errorMessage} サーバーで受付が確認されませんでした。同じ送信IDで再送するため、もう一度［文字起こしを開始］を押してください。`
        : `${errorMessage} 受付状況を確認できません。前回の送信IDを保護しています。接続回復後にもう一度［文字起こしを開始］を押すか、ページを再読み込みしてください。`,
      true
    );
    return;
  }
  const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** attempt));
  const message = document.querySelector('#progress-message');
  if (message) message.textContent = `送信の受付状況を確認しています… ${Math.ceil(delay / 1000)}秒後に再試行します。`;
  if (cancelButton) cancelButton.disabled = true;
  window.setTimeout(() => {
    if (recoveryGeneration === jobFlowGeneration) {
      recoverSubmittedJob(
        errorMessage,
        submissionId,
        attempt + 1,
        recoveryGeneration,
        confirmedAbsent
      );
    }
  }, delay);
}

listen(form, 'submit', async event => {
  event.preventDefault();
  setAlert(formError, '');
  const unresolvedSubmissionId = storedPendingSubmissionId();
  const retryUnacceptedSubmission = Boolean(
    unresolvedSubmissionId && pendingSubmissionRetryAllowed(unresolvedSubmissionId)
  );
  if (unresolvedSubmissionId && !retryUnacceptedSubmission) {
    const recoveryGeneration = ++jobFlowGeneration;
    setRunning(true);
    showProgressCard({scroll: true});
    if (cancelButton) cancelButton.disabled = true;
    const message = document.querySelector('#progress-message');
    if (message) message.textContent = '前回の送信結果を再確認しています…';
    await recoverSubmittedJob(
      '前回の送信結果がまだ確認できません。',
      unresolvedSubmissionId,
      0,
      recoveryGeneration
    );
    return;
  }
  if (!sourcePath.value.trim() && !(inputFile && inputFile.files && inputFile.files.length)) {
    setAlert(formError, '処理する音声・動画ファイルを選択してください。', true);
    const sourceSection = document.querySelector('#setup-source');
    if (sourceSection) sourceSection.scrollIntoView({behavior: 'smooth', block: 'start'});
    return;
  }
  const readiness = createReadiness();
  if (!readiness.ready) {
    setAlert(formError, readiness.blockers.join('。') || 'モデル取得・接続確認の注意事項を確認してください。', true);
    setMobileStep(3);
    return;
  }
  const provider = aiProvider ? aiProvider.value : 'none';
  if (selectedTranscriptFinishingMode() === 'advanced' && provider === 'none') {
    setAlert(formError, '高度モードでは OpenAI、Google Gemini、またはローカルLLMを選択してください。', true);
    openSettingsPanel('finishing');
    return;
  }
  if (provider === 'none') aiOptionInputs.forEach(input => { input.checked = false; });
  const wantsAi = provider !== 'none' && aiOptionInputs.some(input => input.checked);
  if (wantsAi && provider === 'none') {
    setAlert(formError, 'AI 機能を使う場合は OpenAI、Google Gemini、またはローカルLLMを選択してください。', true);
    return;
  }
  // Disabled form controls are omitted from FormData. Capture every selected
  // option, especially source_path/input_file, before locking the form.
  const jobFormData = new FormData(form);
  const submissionId = retryUnacceptedSubmission
    ? unresolvedSubmissionId
    : createSubmissionId();
  const submissionGeneration = ++jobFlowGeneration;
  storePendingSubmissionId(submissionId);
  let responseStatus = null;
  setRunning(true);
  showProgressCard({scroll: true});
  try {
    const response = await apiFetch('/api/jobs', {
      method: 'POST',
      headers: {'X-Gurumoji-Submission-Id': submissionId},
      body: jobFormData
    });
    responseStatus = response.status;
    const data = await readJsonResponse(response);
    if (submissionGeneration !== jobFlowGeneration) return;
    if (response.status === 409) {
      let activeJob = jobFromPayload(data);
      if (!activeJob) {
        try { activeJob = await fetchActiveJob(); } catch (_) { activeJob = null; }
      }
      if (submissionGeneration !== jobFlowGeneration) return;
      if (activeJob) {
        pollFailureCount = 0;
        resumeJob(activeJob, {scroll: true});
        setAlert(formError, data.error || '実行中の文字起こしへ再接続しました。', true);
        return;
      }
    }
    if (!response.ok) throw new Error(data.error || '処理を開始できませんでした。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (submissionGeneration !== jobFlowGeneration) return;
    clearPollTimer();
    activeJobId = null;
    if (cancelButton) cancelButton.disabled = true;
    if (responseStatus !== null && responseStatus >= 400 && responseStatus < 500) {
      storePendingSubmissionId('');
      setRunning(false);
      if (progressCard) progressCard.hidden = true;
      setAlert(formError, error.message, true);
      return;
    }
    await recoverSubmittedJob(error.message, submissionId, 0, submissionGeneration);
  }
});

async function pollJob() {
  if (!activeJobId) return;
  const requestedJobId = activeJobId;
  try {
    const response = await apiFetch(`/api/jobs/${encodeURIComponent(requestedJobId)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (requestedJobId !== activeJobId) return;
    if (response.status === 404) {
      const persistedJob = await fetchPersistedJob(requestedJobId);
      if (persistedJob) {
        pollFailureCount = 0;
        resumeJob(persistedJob);
        return;
      }
      let activeJob = null;
      try { activeJob = await fetchActiveJob(); } catch (_) { activeJob = null; }
      if (activeJob) {
        pollFailureCount = 0;
        resumeJob(activeJob);
        return;
      }
      clearPollTimer();
      storeActiveJobId('');
      activeJobId = null;
      setRunning(false);
      if (cancelButton) cancelButton.disabled = true;
      throw new Error(data.error || '実行中ジョブが見つかりません。アプリを再起動した可能性があります。');
    }
    if (!response.ok) throw new Error(data.error || '進捗を取得できません。');
    pollFailureCount = 0;
    resumeJob(data);
  } catch (error) {
    if (!activeJobId || !jobRunning) {
      document.querySelector('#progress-message').textContent = error.message;
      return;
    }
    pollFailureCount += 1;
    const delay = Math.min(pollMaxDelayMs, pollBaseDelayMs * (2 ** Math.min(pollFailureCount - 1, 5)));
    document.querySelector('#progress-message').textContent = `${error.message} ${Math.ceil(delay / 1000)}秒後に再接続します…`;
    schedulePoll(delay);
  }
}

function fallbackProgressStage(job, progress) {
  if (job.status === 'admitting') return {label: '送信データの受付', progress: 0};
  if (job.status === 'queued') return {label: '開始準備', progress: 0};
  if (job.status === 'committing') return {label: '結果ファイルの保存', progress: Math.max(75, progress)};
  if (job.status === 'completed') return {label: '処理完了', progress: 100};
  const stages = [
    [0, 8, '処理環境の確認'],
    [8, 52, '文字起こし'],
    [52, 64, '発話時刻の補正'],
    [64, 80, '話者の分離'],
    [80, 88, '文字起こしの仕上げ'],
    [88, 90, '音声感情の分析'],
    [90, 94, '話者名の確認'],
    [94, 97, '議題アウトラインの作成'],
    [97, 100, '結果ファイルの保存']
  ];
  const stage = stages.find(([start, end]) => progress >= start && progress < end) || stages.at(-1);
  const [start, end, label] = stage;
  return {label, progress: Math.round(100 * (progress - start) / Math.max(1, end - start))};
}

function renderAiTokenUsage(rootSelector, rawUsage) {
  const root = document.querySelector(rootSelector);
  if (!root) return;
  const usage = rawUsage && typeof rawUsage === 'object' ? rawUsage : {};
  const provider = String(usage.provider || '').toLowerCase();
  const requestCount = Math.max(0, Number(usage.request_count) || 0);
  const visible = ['openai', 'google', 'lmstudio'].includes(provider) && requestCount > 0;
  root.hidden = !visible;
  if (!visible) return;
  const format = value => new Intl.NumberFormat('ja-JP').format(Math.max(0, Number(value) || 0));
  const providerElement = root.querySelector('[data-ai-provider]');
  const modelElement = root.querySelector('[data-ai-model]');
  const inputElement = root.querySelector('[data-ai-input]');
  const outputElement = root.querySelector('[data-ai-output]');
  const totalElement = root.querySelector('[data-ai-total]');
  const requestsElement = root.querySelector('[data-ai-requests]');
  if (providerElement) providerElement.textContent = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[provider] || 'AI';
  if (modelElement) modelElement.textContent = String(usage.model || '');
  if (inputElement) inputElement.textContent = format(usage.input_tokens);
  if (outputElement) outputElement.textContent = format(usage.output_tokens);
  if (totalElement) totalElement.textContent = format(usage.total_tokens);
  if (requestsElement) requestsElement.textContent = `${format(requestCount)}回`;
  const optionalDetails = [
    ['[data-ai-cached]', usage.cached_tokens],
    ['[data-ai-reasoning]', usage.reasoning_tokens]
  ];
  optionalDetails.forEach(([selector, value]) => {
    const element = root.querySelector(selector);
    const count = Math.max(0, Number(value) || 0);
    if (!element) return;
    element.hidden = count <= 0;
    const number = element.querySelector('b');
    if (number) number.textContent = format(count);
  });
  const unreported = root.querySelector('[data-ai-unreported]');
  if (unreported) unreported.hidden = Boolean(usage.reported);
}

function renderProgress(job) {
  lastProgressJob = job;
  if (typeof renderAiFinishingActivity === 'function') renderAiFinishingActivity(job);
  const progress = Number(job.progress || 0);
  const fallbackStage = fallbackProgressStage(job, progress);
  const hasCurrentStage = Boolean(job.stage_label)
    && !(job.stage === 'queued' && job.status === 'running' && progress > 0);
  const stageLabel = hasCurrentStage ? job.stage_label : fallbackStage.label;
  const stageProgress = Math.max(0, Math.min(100, Number(
    hasCurrentStage ? job.stage_progress : fallbackStage.progress
  ) || 0));
  const active = ['admitting', 'queued', 'running', 'committing'].includes(job.status);
  const activityLabels = {
    admitting: 'RECEIVING', queued: 'WAITING', running: 'RUNNING', committing: 'SAVING',
    completed: 'COMPLETED', failed: 'ERROR', cancelled: 'STOPPED'
  };
  progressCard.classList.toggle('is-active', active);
  progressCard.classList.toggle('has-error', ['failed', 'cancelled'].includes(job.status));
  document.querySelector('#progress-number').textContent = `${progress}%`;
  document.querySelector('#progress-bar').style.width = `${progress}%`;
  document.querySelector('#progress-overall-track').setAttribute('aria-valuenow', String(progress));
  document.querySelector('#progress-stage-label').textContent = stageLabel;
  document.querySelector('#progress-stage-number').textContent = `${stageProgress}%`;
  document.querySelector('#progress-stage-bar').style.width = `${stageProgress}%`;
  document.querySelector('#progress-stage-track').setAttribute('aria-valuenow', String(stageProgress));
  document.querySelector('#progress-activity-label').textContent = activityLabels[job.status] || 'WORKING';
  document.querySelector('#progress-message').textContent = job.message || '';
  document.querySelector('#progress-log').textContent = (job.logs || []).join('\n');
  renderAiTokenUsage('#progress-ai-usage', job.ai_usage);
  const titles = {admitting: '受付中', queued: '開始待ち', running: '文字起こし中', committing: '結果を保存中', completed: '処理完了', failed: 'エラー', cancelled: '中止しました'};
  document.querySelector('#progress-title').textContent = titles[job.status] || '処理中';
  document.querySelector('#progress-message').style.color = ['failed', 'cancelled'].includes(job.status) ? '#913733' : '';
  updateJobChip(job);
  syncCreateViewState();
}

listen(cancelButton, 'click', async () => {
  if (!activeJobId) return;
  if (!window.confirm('実行中の文字起こし・AI処理を中止しますか？\n中止した処理は、この画面から続きを実行できません。')) return;
  cancelButton.disabled = true;
  try {
    const response = await apiFetch(`/api/jobs/${activeJobId}/cancel`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error);
    document.querySelector('#progress-message').textContent = '中止を要求しました…';
  } catch (error) {
    document.querySelector('#progress-message').textContent = error.message;
    if (jobRunning) cancelButton.disabled = false;
  }
});

function updateFacetSelect(select, values, allLabel) {
  const selected = select.value;
  select.replaceChildren(new Option(allLabel, ''));
  values.forEach(value => select.add(new Option(value, value)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function updateLibraryGroupSelect(select, groups, {includeAll = false, includeUngrouped = false} = {}) {
  if (!select) return;
  const selected = select.value;
  select.replaceChildren();
  if (includeAll) select.add(new Option('すべてのフォルダー', ''));
  if (includeAll || includeUngrouped) select.add(new Option('未分類', includeAll ? '__ungrouped__' : ''));
  groups.forEach(group => select.add(new Option(`${group.name}（${group.item_count || 0}件）`, group.id)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

async function assignLibraryItemGroup(item, select) {
  const previous = item.group_id || '';
  select.disabled = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(item.id)}/group`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({group_id: select.value})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'フォルダーを変更できませんでした。');
    await loadLibrary();
  } catch (error) {
    select.value = previous;
    select.disabled = false;
    setAlert(document.querySelector('#library-message'), error.message, true);
  }
}

function renderLibraryGroupManager() {
  if (!libraryGroupList) return;
  libraryGroupList.replaceChildren();
  if (!libraryGroups.length) {
    const empty = document.createElement('p');
    empty.className = 'library-group-empty';
    empty.textContent = 'フォルダーはまだありません。上の欄から作成できます。';
    libraryGroupList.append(empty);
    return;
  }
  libraryGroups.forEach(group => {
    const row = document.createElement('div');
    row.className = 'library-group-row';
    const field = document.createElement('label');
    field.className = 'field';
    const label = document.createElement('span');
    label.textContent = `${group.item_count || 0}件`;
    const input = document.createElement('input');
    input.type = 'text';
    input.maxLength = 80;
    input.value = group.name;
    input.setAttribute('aria-label', `${group.name}のフォルダー名`);
    field.append(label, input);
    const save = document.createElement('button');
    save.type = 'button';
    save.className = 'secondary-button compact-button';
    save.textContent = '名前を保存';
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({name: input.value})
        });
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダー名を変更できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, 'フォルダー名を変更しました。');
      } catch (error) {
        save.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'secondary-button danger compact-button';
    remove.textContent = '削除';
    remove.addEventListener('click', async () => {
      const count = Number(group.item_count || 0);
      const note = count ? `\n所属する${count}件のデータは「未分類」に戻ります。` : '';
      if (!window.confirm(`フォルダー「${group.name}」を削除しますか？${note}\n処理済みデータ本体は削除されません。`)) return;
      remove.disabled = true;
      try {
        const response = await apiFetch(`/api/library/groups/${encodeURIComponent(group.id)}`, {method: 'DELETE'});
        const data = await readJsonResponse(response);
        if (!response.ok) throw new Error(data.error || 'フォルダーを削除できませんでした。');
        await loadLibrary();
        renderLibraryGroupManager();
        setAlert(libraryGroupMessage, `「${group.name}」を削除しました。`);
      } catch (error) {
        remove.disabled = false;
        setAlert(libraryGroupMessage, error.message, true);
      }
    });
    row.append(field, save, remove);
    libraryGroupList.append(row);
  });
}

function libraryFilterState() {
  return {
    keyword: document.querySelector('#library-keyword').value.trim(),
    speaker: document.querySelector('#library-speaker').value,
    emotion: document.querySelector('#library-emotion').value,
    group: document.querySelector('#library-group').value,
    data_group: document.querySelector('#library-data-group')?.value || '',
    tag: document.querySelector('#library-tag')?.value || '',
    sort: document.querySelector('#library-sort').value,
    recorded_from: document.querySelector('#library-recorded-from')?.value || '',
    recorded_to: document.querySelector('#library-recorded-to')?.value || '',
    media_duration_min: document.querySelector('#library-media-duration-min')?.value || '',
    media_duration_max: document.querySelector('#library-media-duration-max')?.value || ''
  };
}

function updateLibraryFilterState() {
  const state = libraryFilterState();
  const conditions = [];
  if (state.keyword) conditions.push(`「${state.keyword}」`);
  if (state.speaker) conditions.push(`話者: ${state.speaker}`);
  if (state.emotion) conditions.push(`感情: ${state.emotion}`);
  if (state.data_group) conditions.push(`分析グループ: ${document.querySelector('#library-data-group').selectedOptions[0].textContent}`);
  if (state.tag) conditions.push(`タグ: ${document.querySelector('#library-tag').selectedOptions[0].textContent}`);
  if (state.recorded_from) conditions.push(`収録日: ${state.recorded_from}以降`);
  if (state.recorded_to) conditions.push(`収録日: ${state.recorded_to}以前`);
  if (state.media_duration_min) conditions.push(`メディア: ${state.media_duration_min}秒以上`);
  if (state.media_duration_max) conditions.push(`メディア: ${state.media_duration_max}秒以下`);
  if (state.group) {
    const group = document.querySelector('#library-group');
    conditions.push(`フォルダー: ${group.options[group.selectedIndex].text}`);
  }
  if (state.sort !== 'updated_desc') {
    const sort = document.querySelector('#library-sort');
    conditions.push(`並び: ${sort.options[sort.selectedIndex].text}`);
  }
  const summary = document.querySelector('#library-filter-summary');
  const badge = document.querySelector('#library-filter-badge');
  const clear = document.querySelector('#library-clear-filters');
  if (summary) summary.textContent = conditions.length
    ? `${conditions.join(' / ')} で表示しています`
    : 'すべてのデータを表示しています';
  if (badge) badge.textContent = conditions.length ? `${conditions.length}条件` : '条件なし';
  if (clear) clear.disabled = conditions.length === 0;
}

function renderLibraryLoading() {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  for (let index = 0; index < 3; index += 1) {
    const skeleton = document.createElement('div');
    skeleton.className = 'library-skeleton';
    skeleton.setAttribute('aria-hidden', 'true');
    skeleton.innerHTML = '<i></i><div><b></b><span></span><span></span></div>';
    list.append(skeleton);
  }
}

function renderLibraryOverview(items) {
  const hasTime = item => item.duration !== null && item.duration !== undefined && item.duration !== ''
    && typeof item.duration !== 'boolean' && Number.isFinite(Number(item.duration)) && Number(item.duration) >= 0;
  const known = items.filter(hasTime);
  const duration = known.reduce((sum, item) => sum + Number(item.duration), 0);
  const missing = items.filter(item => !hasTime(item) || item.missing_time_turn_count > 0).length;
  const speakers = new Set(items.flatMap(item => item.speakers || []));
  const latest = items.reduce((value, item) => {
    const updated = String(item.updated_at || '');
    return updated > value ? updated : value;
  }, '');
  const values = {
    '#library-total-metric': String(items.length),
    '#library-duration-metric': !items.length ? '—' : !known.length ? '時刻不明'
      : missing ? `時刻あり計 ${formatTime(duration)} / 欠測あり${missing}件` : formatTime(duration),
    '#library-speaker-metric': String(speakers.size),
    '#library-updated-metric': latest ? formatDate(latest) : '—'
  };
  Object.entries(values).forEach(([selector, value]) => {
    const element = document.querySelector(selector);
    if (element) element.textContent = value;
  });
}

// DATA-01: deleted conversations wait in the trash until restored, purged or expired.
async function loadLibraryTrash() {
  const panel = document.querySelector('#library-trash');
  if (!panel) return;
  const list = panel.querySelector('[data-trash-list]');
  try {
    const response = await apiFetch('/api/library/trash', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'ゴミ箱を読み込めませんでした。');
    const entries = data.entries || [];
    const days = Number(data.retention_days || 0);
    panel.querySelector('[data-trash-summary]').textContent = `（${entries.length}件・${formatBytes(data.total_bytes || 0)}）`;
    panel.querySelector('[data-trash-note]').textContent = days
      ? `削除した会話はここに移り、${days}日後に自動で完全に削除されます。それまでは復元できます。`
      : '削除した会話はここに移り、完全に削除するまで残ります（自動削除なし）。';
    list.replaceChildren();
    if (!entries.length) {
      list.textContent = 'ゴミ箱は空です。';
      return;
    }
    entries.forEach(entry => {
      const row = document.createElement('div');
      row.className = 'library-trash-row';
      const label = document.createElement('span');
      label.textContent = `${entry.source_name || entry.item_id} / 削除 ${formatDate(entry.deleted_at)}`
        + `${entry.expires_at ? ` / 自動削除 ${formatDate(entry.expires_at)}` : ''} / ${formatBytes(entry.bytes || 0)}`;
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.className = 'secondary-button compact-button';
      restore.textContent = '復元';
      restore.disabled = !entry.restorable;
      restore.addEventListener('click', () => changeLibraryTrash(entry, 'restore'));
      const purge = document.createElement('button');
      purge.type = 'button';
      purge.className = 'secondary-button compact-button danger';
      purge.textContent = '完全に削除';
      purge.addEventListener('click', () => changeLibraryTrash(entry, 'purge'));
      row.append(label, restore, purge);
      list.append(row);
    });
  } catch (error) {
    list.textContent = error.message;
  }
}

async function changeLibraryTrash(entry, action) {
  const name = entry.source_name || entry.item_id;
  if (action === 'purge' && !window.confirm(`「${name}」をゴミ箱から完全に削除しますか？\n元に戻せません。`)) return;
  const message = document.querySelector('#library-message');
  try {
    const url = `/api/library/trash/${encodeURIComponent(entry.id)}${action === 'restore' ? '/restore' : ''}`;
    const response = await apiFetch(url, {method: action === 'restore' ? 'POST' : 'DELETE'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '操作できませんでした。');
    if (action === 'restore') await loadLibrary(); else await loadLibraryTrash();
    setAlert(message, `「${name}」：${data.message}`);
  } catch (error) {
    setAlert(message, error.message, true);
  }
}

async function loadLibrary(pageOffset = 0) {
  const list = document.querySelector('#library-list');
  const message = document.querySelector('#library-message');
  setAlert(message, '');
  updateLibraryFilterState();
  const state = libraryFilterState();
  const filterKey = JSON.stringify(state);
  libraryPageOffset = filterKey === libraryPageFilter && Number.isInteger(pageOffset) ? pageOffset : 0;
  libraryPageFilter = filterKey;
  const params = new URLSearchParams(state);
  params.set('limit', '50'); params.set('offset', String(libraryPageOffset));
  // Preserve the existing unfiltered request shape for offline fixtures and clients.
  ['recorded_from', 'recorded_to', 'media_duration_min', 'media_duration_max', 'data_group', 'tag'].forEach(key => {
    if (state[key] === '') params.delete(key);
  });
  if (libraryRequestController) libraryRequestController.abort();
  libraryRequestController = new AbortController();
  const requestId = ++libraryRequestSequence;
  list.setAttribute('aria-busy', 'true');
  renderLibraryLoading();
  try {
    const response = await apiFetch(`/api/library?${params}`, {signal: libraryRequestController.signal});
    const data = await readJsonResponse(response);
    if (requestId !== libraryRequestSequence) return;
    if (!response.ok) throw new Error(data.error || '処理済みデータの一覧を取得できません。');
    updateFacetSelect(document.querySelector('#library-speaker'), data.facets.speakers || [], 'すべての話者');
    updateFacetSelect(document.querySelector('#library-emotion'), data.facets.emotions || [], 'すべての感情');
    libraryGroups = Array.isArray(data.groups) ? data.groups : [];
    document.dispatchEvent(new CustomEvent('gurumoji-library-catalog', {detail: data}));
    updateLibraryGroupSelect(document.querySelector('#library-group'), libraryGroups, {includeAll: true});
    const items = data.items || [];
    document.querySelector('#library-count').textContent = `${data.total}件中 ${libraryPageOffset + (items.length ? 1 : 0)}〜${libraryPageOffset + items.length}件を表示`;
    const pager = document.querySelector('#library-pagination');
    if (pager) {
      pager.replaceChildren();
      const previous = contentButton('前の50件', () => loadLibrary(Math.max(0, libraryPageOffset - 50)));
      previous.disabled = libraryPageOffset === 0;
      const next = contentButton('次の50件', () => loadLibrary(libraryPageOffset + 50));
      next.disabled = !data.pagination?.has_more;
      pager.append(previous, next);
    }
    renderLibraryOverview(items);
    renderLibraryItems(items);
    updateLibraryFilterState();
    loadLibraryTrash();
    if (!trainingStatusLoaded) loadTrainingStatus();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== libraryRequestSequence) return;
    list.replaceChildren();
    setAlert(message, error.message, true);
  } finally {
    if (requestId === libraryRequestSequence) list.setAttribute('aria-busy', 'false');
  }
}

function renderLibraryItems(items) {
  const list = document.querySelector('#library-list');
  list.replaceChildren();
  if (!items.length) {
    const empty = document.createElement('div');
    empty.className = 'library-empty';
    const title = document.createElement('strong');
    title.textContent = '条件に一致するデータはありません';
    const description = document.createElement('p');
    description.textContent = '検索条件を変えるか、新しい文字起こしを始めてください。';
    const actions = document.createElement('div');
    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'secondary-button';
    clear.textContent = '条件をクリア';
    clear.addEventListener('click', clearLibraryFilters);
    const create = document.createElement('button');
    create.type = 'button';
    create.className = 'primary-button small';
    create.textContent = '＋ 新しい文字起こし';
    create.addEventListener('click', () => showView('new'));
    actions.append(clear, create);
    empty.append(title, description, actions);
    list.append(empty);
    return;
  }
  const grouped = document.querySelector('#library-sort').value === 'group';
  const visibleGroupCounts = items.reduce((counts, item) => {
    const key = item.group_id || '__ungrouped__';
    counts.set(key, (counts.get(key) || 0) + 1);
    return counts;
  }, new Map());
  let previousGroupKey = null;
  items.forEach(item => {
    const groupKey = item.group_id || '__ungrouped__';
    if (grouped && groupKey !== previousGroupKey) {
      const heading = document.createElement('div');
      heading.className = 'library-group-heading';
      const name = document.createElement('strong');
      name.textContent = item.group_name || '未分類';
      const count = document.createElement('span');
      count.textContent = `${visibleGroupCounts.get(groupKey) || 0}件`;
      heading.append(name, count);
      list.append(heading);
      previousGroupKey = groupKey;
    }
    const card = document.createElement('article');
    card.className = 'library-item';
    const media = document.createElement('div');
    media.className = 'library-media';
    const thumbnail = document.createElement('img');
    thumbnail.className = 'library-thumbnail';
    thumbnail.src = item.thumbnail_url;
    thumbnail.alt = `${item.source_name} のワードクラウド`;
    thumbnail.loading = 'lazy';
    const mediaFallback = document.createElement('span');
    mediaFallback.className = 'library-media-fallback';
    mediaFallback.textContent = 'プレビューなし';
    const mediaBadge = document.createElement('span');
    mediaBadge.className = 'library-media-badge';
    mediaBadge.textContent = item.media_url ? (item.media_kind === 'video' ? '動画' : '音声') : 'テキスト';
    thumbnail.addEventListener('error', () => {
      media.classList.add('unavailable');
      thumbnail.remove();
    });
    media.append(thumbnail, mediaFallback, mediaBadge);
    const body = document.createElement('div');
    body.className = 'library-item-body';
    const heading = document.createElement('div');
    heading.className = 'library-item-heading';
    const title = document.createElement('h3');
    title.textContent = item.source_name;
    const updated = document.createElement('time');
    updated.dateTime = item.updated_at || '';
    updated.textContent = `更新 ${formatDate(item.updated_at)}`;
    heading.append(title, updated);
    const meta = document.createElement('div');
    meta.className = 'library-meta';
    const mediaLabel = item.media_url ? (item.media_kind === 'video' ? '動画あり' : '音声あり') : '元メディアなし';
    [
      `発話 ${item.segment_count}件`,
      `収録日 ${item.media_created_at ? String(item.media_created_at).slice(0, 10) : '不明'}`,
      `メディア ${item.media_duration_seconds == null ? '不明' : item.media_duration_seconds < 1 ? `${item.media_duration_seconds}秒` : formatTime(item.media_duration_seconds)}`,
      `最終時刻 ${analysisEndpointText(item.duration, item.timed_turn_count, item.missing_time_turn_count)}`,
      mediaLabel,
      `修正 ${item.revision_count}回`
    ].forEach(value => {
      const metric = document.createElement('span');
      metric.textContent = value;
      meta.append(metric);
    });
    const preview = document.createElement('p');
    preview.className = 'library-preview';
    preview.textContent = item.preview || '本文はまだありません。';
    const chips = document.createElement('div');
    chips.className = 'library-chips';
    if (item.group_name) {
      const chip = document.createElement('span');
      chip.className = 'library-chip group';
      chip.textContent = item.group_name;
      chips.append(chip);
    }
    (item.speakers || []).slice(0, 5).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = value;
      chips.append(chip);
    });
    if ((item.speakers || []).length > 5) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `＋${item.speakers.length - 5}人`;
      chips.append(chip);
    }
    (item.emotions || []).forEach(value => {
      const chip = document.createElement('span');
      chip.className = 'library-chip emotion';
      chip.textContent = value;
      chips.append(chip);
    });
    if (item.match_count) {
      const chip = document.createElement('span');
      chip.className = 'library-chip';
      chip.textContent = `キーワード一致 ${item.match_count}発話`;
      chips.append(chip);
    }
    body.append(heading, meta, preview, chips);
    const actions = document.createElement('div');
    actions.className = 'library-actions';
    const groupLabel = document.createElement('label');
    groupLabel.className = 'library-group-assignment';
    const groupLabelText = document.createElement('span');
    groupLabelText.className = 'visually-hidden';
    groupLabelText.textContent = `${item.source_name}のフォルダー`;
    const groupSelect = document.createElement('select');
    groupSelect.setAttribute('aria-label', `${item.source_name}のフォルダー`);
    updateLibraryGroupSelect(groupSelect, libraryGroups, {includeUngrouped: true});
    groupSelect.value = item.group_id || '';
    groupSelect.addEventListener('click', event => event.stopPropagation());
    groupSelect.addEventListener('change', () => assignLibraryItemGroup(item, groupSelect));
    groupLabel.append(groupLabelText, groupSelect);
    const open = document.createElement('button');
    open.className = 'library-card-open';
    open.type = 'button';
    open.setAttribute('aria-label', `${item.source_name}を開いて編集`);
    open.addEventListener('click', () => openLibraryItem(item.id));
    const analyze = document.createElement('button');
    analyze.className = 'library-analysis-button';
    analyze.type = 'button';
    analyze.textContent = '分析・可視化';
    analyze.setAttribute('aria-label', `${item.source_name}を分析・可視化`);
    analyze.addEventListener('click', () => openAnalysisForItem(item.id));
    const remove = document.createElement('button');
    remove.className = 'library-delete-button';
    remove.type = 'button';
    remove.textContent = '削除';
    remove.setAttribute('aria-label', `${item.source_name}を削除`);
    remove.addEventListener('click', () => deleteLibraryItem(item.id, item.source_name));
    actions.append(groupLabel, analyze, remove);
    card.append(open, media, body, actions);
    list.append(card);
  });
}

async function loadTrainingStatus() {
  const container = document.querySelector('#training-status');
  if (trainingStatusLoaded) return;
  trainingStatusLoaded = true;
  try {
    const response = await apiFetch('/api/training');
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '学習履歴を確認できませんでした。');
    container.replaceChildren();
    const label = document.createElement('span');
    label.textContent = `くしなだ学習データ: ${data.event_count}件（音声＋感情 ${data.ready_count}件）`;
    container.append(label);
    if (data.jsonl_url) {
      const link = document.createElement('a');
      link.href = data.jsonl_url;
      link.textContent = 'JSONL';
      link.download = '';
      container.append(link);
    }
    if (data.manifest_url) {
      const link = document.createElement('a');
      link.href = data.manifest_url;
      link.textContent = 'CSV';
      link.download = '';
      container.append(link);
    }
  } catch (error) {
    trainingStatusLoaded = false;
    container.textContent = error.message || '学習履歴を確認できませんでした。';
  }
}

['#library-speaker', '#library-emotion', '#library-group', '#library-sort', '#library-recorded-from', '#library-recorded-to', '#library-media-duration-min', '#library-media-duration-max'].forEach(selector => {
  listen(document.querySelector(selector), 'change', () => loadLibrary());
});
listen(document.querySelector('#library-keyword'), 'input', () => {
  window.clearTimeout(libraryTimer);
  libraryTimer = window.setTimeout(loadLibrary, 250);
});

function clearLibraryFilters() {
  document.querySelector('#library-keyword').value = '';
  document.querySelector('#library-speaker').value = '';
  document.querySelector('#library-emotion').value = '';
  document.querySelector('#library-group').value = '';
  document.querySelector('#library-sort').value = 'updated_desc';
  ['#library-recorded-from', '#library-recorded-to', '#library-media-duration-min', '#library-media-duration-max', '#library-data-group', '#library-tag'].forEach(selector => {
    const input = document.querySelector(selector);
    if (input) input.value = '';
  });
  updateLibraryFilterState();
  loadLibrary();
}

function setLibraryFiltersOpen(open) {
  if (!libraryCard) return;
  libraryCard.classList.toggle('filters-open', open);
  const toggle = document.querySelector('#library-filter-toggle');
  if (toggle) toggle.setAttribute('aria-expanded', String(open));
}

listen(document.querySelector('#library-clear-filters'), 'click', clearLibraryFilters);
listen(document.querySelector('#library-filter-toggle'), 'click', event => {
  setLibraryFiltersOpen(event.currentTarget.getAttribute('aria-expanded') !== 'true');
});
listen(document.querySelector('#library-refresh-button'), 'click', () => {
  trainingStatusLoaded = false;
  loadLibrary();
});
listen(document.querySelector('#library-create-new-button'), 'click', () => showView('new'));
listen(document.querySelector('#manage-library-groups-button'), 'click', async () => {
  setAlert(libraryGroupMessage, '');
  await loadLibrary();
  renderLibraryGroupManager();
  if (libraryGroupDialog && !libraryGroupDialog.open) libraryGroupDialog.showModal();
});
listen(document.querySelector('#close-library-group-dialog'), 'click', () => {
  if (libraryGroupDialog) libraryGroupDialog.close();
});
listen(document.querySelector('#library-group-create-form'), 'submit', async event => {
  event.preventDefault();
  const input = document.querySelector('#library-group-name');
  const name = String(input && input.value || '').trim();
  if (!name) return;
  const submit = event.currentTarget.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const response = await apiFetch('/api/library/groups', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'グループを作成できませんでした。');
    input.value = '';
    await loadLibrary();
    renderLibraryGroupManager();
    setAlert(libraryGroupMessage, `「${data.name}」を作成しました。`);
  } catch (error) {
    setAlert(libraryGroupMessage, error.message, true);
  } finally {
    submit.disabled = false;
  }
});

function selectedAiModelEntry() {
  if (!aiModelSelect) return null;
  return aiModelCatalog.find(item => item.id === aiModelSelect.value) || null;
}

function updateAiModelDescription() {
  if (!aiModelDescription) return;
  const entry = selectedAiModelEntry();
  aiModelDescription.textContent = entry
    ? (entry.description || `モデルID: ${entry.id}`)
    : 'モデルを選択してください。';
}

function renderAiModelOptions() {
  if (!aiModelSelect) return;
  const query = String(aiModelSearch && aiModelSearch.value || '').trim().toLocaleLowerCase();
  const previous = aiModelSelect.value || String(aiModelDialog && aiModelDialog.dataset.selectedModel || '');
  const visible = aiModelCatalog.filter(item => {
    const haystack = `${item.id} ${item.label || ''} ${item.description || ''}`.toLocaleLowerCase();
    return !query || haystack.includes(query);
  });
  aiModelSelect.replaceChildren();
  visible.forEach(item => {
    const option = document.createElement('option');
    option.value = item.id;
    option.textContent = item.label && item.label !== item.id
      ? `${item.label} (${item.id})`
      : item.id;
    aiModelSelect.append(option);
  });
  if (visible.some(item => item.id === previous)) aiModelSelect.value = previous;
  else if (visible.length) aiModelSelect.selectedIndex = 0;
  if (saveAiModelButton) saveAiModelButton.disabled = visible.length === 0;
  updateAiModelDescription();
}

async function openAiModelDialog(provider) {
  const normalizedProvider = String(provider || '').trim().toLowerCase();
  if (!['openai', 'google', 'lmstudio'].includes(normalizedProvider)) return;
  const label = {
    openai: 'OpenAI',
    google: 'Google Gemini',
    lmstudio: String(tokenConfigSnapshot.local_llm_label || 'LM Studio（ローカル）')
  }[normalizedProvider];
  if (normalizedProvider !== 'lmstudio' && !tokenConfigSnapshot[normalizedProvider]) {
    window.alert(`${label} APIキーがtokens.jsonに設定されていません。`);
    return;
  }
  activeAiModelProvider = normalizedProvider;
  aiModelCatalog = [];
  if (aiModelProviderLabel) aiModelProviderLabel.textContent = label;
  if (aiModelCurrent) aiModelCurrent.textContent = String(tokenConfigSnapshot[`${normalizedProvider}_model`] || '読込中…');
  if (aiModelSearch) aiModelSearch.value = '';
  if (aiModelDescription) aiModelDescription.textContent = 'APIから利用可能なモデルを取得しています…';
  setAlert(aiModelError, '');
  if (aiModelSelect) {
    const loadingOption = document.createElement('option');
    loadingOption.textContent = 'モデル一覧を読込中…';
    loadingOption.disabled = true;
    aiModelSelect.replaceChildren(loadingOption);
  }
  if (saveAiModelButton) saveAiModelButton.disabled = true;
  if (!aiModelDialog || typeof aiModelDialog.showModal !== 'function') {
    window.alert('このブラウザではモデル選択画面を開けません。');
    return;
  }
  if (!aiModelDialog.open) aiModelDialog.showModal();
  try {
    const response = await apiFetch(`/api/ai/models?provider=${encodeURIComponent(normalizedProvider)}`, {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'モデル一覧を取得できませんでした。');
    const selected = String(data.selected_model || '').trim();
    const models = Array.isArray(data.models) ? data.models : [];
    aiModelCatalog = models
      .map(item => ({
        id: String(item && item.id || '').trim(),
        label: String(item && item.label || '').trim(),
        description: String(item && item.description || '').trim()
      }))
      .filter(item => item.id);
    if (selected && !aiModelCatalog.some(item => item.id === selected)) {
      aiModelCatalog.unshift({
        id: selected,
        label: selected,
        description: 'tokens.jsonで現在選択されているモデルです。'
      });
    }
    aiModelDialog.dataset.selectedModel = selected;
    if (aiModelCurrent) aiModelCurrent.textContent = selected || '未設定';
    renderAiModelOptions();
    window.requestAnimationFrame(() => aiModelSearch && aiModelSearch.focus());
  } catch (error) {
    if (aiModelSelect) aiModelSelect.replaceChildren();
    if (aiModelDescription) aiModelDescription.textContent = '';
    setAlert(aiModelError, error.message, true);
  }
}

document.querySelectorAll('[data-model-provider]').forEach(button => {
  listen(button, 'click', () => openAiModelDialog(button.dataset.modelProvider));
});
listen(document.querySelector('#cancel-ai-model-button'), 'click', () => {
  if (aiModelDialog) aiModelDialog.close();
});
listen(aiModelSearch, 'input', renderAiModelOptions);
listen(aiModelSelect, 'change', updateAiModelDescription);
listen(aiModelForm, 'submit', async event => {
  event.preventDefault();
  const model = String(aiModelSelect && aiModelSelect.value || '').trim();
  if (!activeAiModelProvider || !model) {
    setAlert(aiModelError, 'モデルを選択してください。', true);
    return;
  }
  setAlert(aiModelError, '');
  if (saveAiModelButton) saveAiModelButton.disabled = true;
  try {
    const response = await apiFetch('/api/ai/model', {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({provider: activeAiModelProvider, model})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'モデル設定を保存できませんでした。');
    if (aiModelDialog) aiModelDialog.close();
    await loadConfig();
    setAlert(document.querySelector('#token-message'), `${model} をtokens.jsonに保存しました。`);
  } catch (error) {
    setAlert(aiModelError, error.message, true);
    if (saveAiModelButton) saveAiModelButton.disabled = false;
  }
});

const addRecordDialog = document.querySelector('#add-record-dialog');
const addRecordForm = document.querySelector('#add-record-form');
const addRecordName = document.querySelector('#add-record-name');

function openAddRecordDialog() {
  setAlert(document.querySelector('#add-record-error'), '');
  if (addRecordName) addRecordName.value = '';
  if (addRecordDialog && typeof addRecordDialog.showModal === 'function') {
    addRecordDialog.showModal();
    window.requestAnimationFrame(() => addRecordName && addRecordName.focus());
    return;
  }
  const fallbackName = window.prompt('追加するデータの名前を入力してください。', '新規文字起こし');
  if (fallbackName && fallbackName.trim()) createEmptyLibraryRecord(fallbackName.trim());
}

async function createEmptyLibraryRecord(sourceName) {
  try {
    const response = await apiFetch('/api/library', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({source_name: sourceName})
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '追加できませんでした。');
    if (addRecordDialog && addRecordDialog.open) addRecordDialog.close();
    renderResult(data);
  } catch (error) {
    const target = addRecordDialog && addRecordDialog.open
      ? document.querySelector('#add-record-error')
      : document.querySelector('#library-message');
    setAlert(target, error.message, true);
  } finally {
    const button = document.querySelector('#confirm-add-record-button');
    if (button) button.disabled = false;
  }
}

listen(document.querySelector('#add-record-button'), 'click', openAddRecordDialog);
listen(document.querySelector('#cancel-add-record-button'), 'click', () => {
  if (addRecordDialog) addRecordDialog.close();
});
listen(addRecordForm, 'submit', event => {
  event.preventDefault();
  if (!addRecordName || !addRecordName.reportValidity()) return;
  const button = document.querySelector('#confirm-add-record-button');
  if (button) button.disabled = true;
  createEmptyLibraryRecord(addRecordName.value.trim());
});

let resultRequestSequence = 0;

async function openLibraryItem(itemId) {
  const requestSequence = ++resultRequestSequence;
  try {
    const response = await apiFetch(`/api/library/${itemId}`);
    const data = await readJsonResponse(response);
    if (requestSequence !== resultRequestSequence) return;
    if (!response.ok) throw new Error(data.error || 'データを開けませんでした。');
    renderResult(data);
  } catch (error) {
    if (requestSequence === resultRequestSequence) {
      setAlert(document.querySelector('#library-message'), error.message, true);
    }
  }
}

function deleteRecoveryNote(data) {
  const paths = Array.isArray(data && data.recovery_paths)
    ? data.recovery_paths
      .map(value => String(value || '').trim())
      .filter(Boolean)
    : [];
  return paths.length ? ` 復旧・確認先: ${paths.join(' / ')}` : '';
}

async function deleteLibraryItem(itemId, name) {
  if (deletingLibraryItems.has(itemId)) return;
  if (!window.confirm(`「${name}」を処理済みデータから削除しますか？\n会話と保存メディアはゴミ箱に移り、保持期間を過ぎると自動で完全に削除されます。それまではゴミ箱から復元できます。出力ファイルと学習履歴は残ります。`)) return;
  deletingLibraryItems.add(itemId);
  const fromResult = currentJobId === itemId && !resultCard.hidden;
  const message = document.querySelector(fromResult ? '#save-message' : '#library-message');
  const suspendedPlayer = currentJobId === itemId ? mediaPlayer : null;
  const suspendedTime = suspendedPlayer?.currentTime || 0;
  const suspendedSource = suspendedPlayer?.getAttribute('src');
  if (fromResult && deleteRecordButton) deleteRecordButton.disabled = true;
  setAlert(message, 'ゴミ箱へ移動しています…');
  try {
    if (suspendedPlayer) {
      suspendedPlayer.pause();
      suspendedPlayer.removeAttribute('src');
      suspendedPlayer.load();
    }
    const response = await apiFetch(`/api/library/${itemId}`, {method: 'DELETE'});
    const data = await readJsonResponse(response);
    const recoveryNote = deleteRecoveryNote(data);
    if (!response.ok) {
      throw new Error(`${data.error || '削除できませんでした。'}${recoveryNote}`);
    }
    if (currentJobId === itemId) {
      currentJobId = null;
      currentJob = null;
      storeActiveJobId('');
      setCurrentJobDirty(false);
    }
    analysisCatalogLoaded = false;
    analysisCatalog = [];
    if (analysisState.itemId === itemId) {
      analysisState.itemId = '';
      analysisState.data = null;
      analysisState.config = {};
      analysisState.annotations = {};
      setAnalysisDirty(false);
    }
    showView('library');
    await loadLibrary();
    const cleanupWarning = data.cleanup_warning || '';
    setAlert(
      document.querySelector('#library-message'),
      `「${name}」をゴミ箱に移しました。${cleanupWarning}${recoveryNote}`,
      Boolean(cleanupWarning || recoveryNote)
    );
  } catch (error) {
    if (suspendedPlayer && suspendedSource && currentJobId === itemId) {
      suspendedPlayer.src = suspendedSource;
      suspendedPlayer.addEventListener('loadedmetadata', () => { suspendedPlayer.currentTime = suspendedTime; }, {once: true});
      suspendedPlayer.load();
    }
    setAlert(message, error.message, true);
  } finally {
    deletingLibraryItems.delete(itemId);
    if (fromResult && deleteRecordButton) deleteRecordButton.disabled = false;
  }
}

function renderDownloads(files) {
  const container = document.querySelector('#download-links');
  container.replaceChildren();
  (files || []).filter(file => !String(file.name || '').toLowerCase().endsWith('.json')).forEach(file => {
    const link = document.createElement('a');
    link.href = file.url;
    link.textContent = `${file.name.split('.').pop().toUpperCase()} を保存`;
    link.setAttribute('download', file.name);
    container.append(link);
  });
}

function meetingPriorityLabel(priority) {
  return ({high: '高', medium: '中', low: '低', unspecified: '未設定'})[priority] || '未設定';
}

function meetingPriorityClass(priority) {
  return ['high', 'medium', 'low'].includes(priority) ? priority : 'unspecified';
}

function appendMeetingMetric(container, label, count, total, className = '') {
  const row = document.createElement('div');
  row.className = `meeting-metric-row${className ? ` ${className}` : ''}`;
  const heading = document.createElement('span');
  heading.textContent = label;
  const bar = document.createElement('i');
  bar.style.width = `${total ? Math.max(4, Math.round((Number(count) || 0) / total * 100)) : 0}%`;
  const value = document.createElement('b');
  value.textContent = String(Number(count) || 0);
  row.append(heading, bar, value);
  container.append(row);
}

function applyMeetingObsidianStatus(data) {
  if (!meetingObsidianStatus || !meetingObsidianSaveButton || !meetingObsidianOpenLink) return;
  const state = data && data.status ? data.status : 'unprepared';
  meetingObsidianStatus.dataset.state = state;
  meetingObsidianStatus.textContent = data?.message || '会議議事録はObsidianに未保存です。';
  meetingObsidianSaveButton.textContent = state === 'stale' ? '更新版をObsidianに保存'
    : state === 'completed' ? 'Obsidianに保存済み' : 'Obsidianに保存';
  meetingObsidianOpenLink.hidden = !data?.uri;
  if (data?.uri) meetingObsidianOpenLink.href = data.uri;
}

async function loadMeetingObsidianStatus(jobId) {
  const generation = ++meetingObsidianStatusGeneration;
  applyMeetingObsidianStatus({status: 'checking', message: 'Obsidianの保存状態を確認しています…'});
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(jobId)}/meeting-obsidian`);
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || 'Obsidianの保存状態を確認できませんでした。');
    if (generation !== meetingObsidianStatusGeneration || currentJobId !== jobId) return;
    applyMeetingObsidianStatus(data);
  } catch (error) {
    if (generation !== meetingObsidianStatusGeneration || currentJobId !== jobId) return;
    applyMeetingObsidianStatus({status: 'error', message: error.message});
  }
}

function renderMeetingMinutes(minutes, jobId) {
  if (!meetingMinutesView) return;
  const data = minutes && typeof minutes === 'object' ? minutes : null;
  const tasks = data && Array.isArray(data.tasks) ? data.tasks : [];
  const decisions = data && Array.isArray(data.decisions) ? data.decisions : [];
  const analysis = data && typeof data.analysis === 'object' && data.analysis ? data.analysis : {};
  const hasMeetingData = data && (tasks.length || decisions.length || Array.isArray(data.summary));
  meetingMinutesView.hidden = !hasMeetingData;
  if (!hasMeetingData) return;

  const prefix = `/api/library/${encodeURIComponent(jobId)}`;
  const exports = [
    ['#meeting-minutes-download', `${prefix}/meeting-minutes.md`],
    ['#meeting-tasks-download', `${prefix}/meeting-tasks.csv`],
    ['#meeting-json-download', `${prefix}/meeting.json`],
  ];
  exports.forEach(([selector, href]) => {
    const link = document.querySelector(selector);
    if (link) link.href = href;
  });

  const method = document.querySelector('#meeting-minutes-method');
  if (method) {
    method.textContent = data.method === 'rule_based_candidate_extraction'
      ? '抽出方法：ルールベースの候補抽出。元発話の時刻を確認してから取り込んでください。'
      : `抽出方法：${data.method || '未記録'}`;
  }
  const summary = document.querySelector('#meeting-minutes-summary');
  summary.replaceChildren();
  (data.summary || []).forEach(text => {
    const item = document.createElement('p');
    item.textContent = text;
    summary.append(item);
  });

  const priorityChart = document.querySelector('#meeting-priority-chart');
  priorityChart.replaceChildren();
  const priorityCounts = analysis.priority_counts || {};
  const priorityTotal = tasks.length || 1;
  [['high', '高'], ['medium', '中'], ['low', '低'], ['unspecified', '未設定']].forEach(([key, label]) => {
    appendMeetingMetric(priorityChart, label, priorityCounts[key], priorityTotal, key);
  });

  const dueSummary = document.querySelector('#meeting-due-summary');
  dueSummary.replaceChildren();
  const dated = tasks.filter(task => task.due_date).length;
  const relative = tasks.filter(task => !task.due_date && task.due_text).length;
  const missing = Math.max(0, tasks.length - dated - relative);
  appendMeetingMetric(dueSummary, '日付あり', dated, tasks.length || 1, 'dated');
  appendMeetingMetric(dueSummary, '期限表現あり', relative, tasks.length || 1, 'relative');
  appendMeetingMetric(dueSummary, '期限未設定', missing, tasks.length || 1, 'missing');

  const speakerChart = document.querySelector('#meeting-speaker-chart');
  speakerChart.replaceChildren();
  const activity = Array.isArray(analysis.speaker_activity) ? analysis.speaker_activity : [];
  const maxSeconds = Math.max(1, ...activity.map(item => Number(item.seconds) || 0));
  activity.slice(0, 6).forEach(item => {
    const row = document.createElement('div');
    row.className = 'meeting-speaker-row';
    const label = document.createElement('span');
    label.textContent = item.speaker || '話者不明';
    const bar = document.createElement('i');
    bar.style.width = `${Math.max(4, Math.round((Number(item.seconds) || 0) / maxSeconds * 100))}%`;
    const value = document.createElement('small');
    value.textContent = `${item.turns || 0}回 / ${formatTime(item.seconds || 0)}`;
    row.append(label, bar, value);
    speakerChart.append(row);
  });
  if (!activity.length) speakerChart.textContent = '発話量データはありません。';

  const taskList = document.querySelector('#meeting-task-list');
  taskList.replaceChildren();
  if (!tasks.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = 'タスク候補は検出されませんでした。録音中の依頼・担当・期限の表現を確認してください。';
    taskList.append(empty);
  }
  tasks.forEach(task => {
    const card = document.createElement('article');
    card.className = 'meeting-task-card';
    const top = document.createElement('div');
    const title = document.createElement('strong');
    title.textContent = task.title || '要確認のタスク候補';
    const priority = document.createElement('span');
    priority.className = `meeting-priority ${meetingPriorityClass(task.priority)}`;
    priority.textContent = `優先度 ${meetingPriorityLabel(task.priority)}`;
    top.append(title, priority);
    const meta = document.createElement('p');
    const due = task.due_date || task.due_text || '未設定';
    meta.textContent = `担当候補: ${task.owner || '未特定'} / 期限: ${due} / 根拠: ${formatTime(task.evidence_start || 0)}`;
    const source = document.createElement('small');
    source.textContent = task.source_text || '';
    card.append(top, meta, source);
    taskList.append(card);
  });

  const decisionList = document.querySelector('#meeting-decision-list');
  decisionList.replaceChildren();
  if (!decisions.length) {
    const empty = document.createElement('p');
    empty.className = 'meeting-empty';
    empty.textContent = '決定事項候補は検出されませんでした。';
    decisionList.append(empty);
  }
  decisions.forEach(decision => {
    const item = document.createElement('article');
    item.className = 'meeting-decision-item';
    const text = document.createElement('p');
    text.textContent = decision.text || '';
    const meta = document.createElement('small');
    meta.textContent = `${decision.speaker || '話者不明'} / ${formatTime(decision.evidence_start || 0)}`;
    item.append(text, meta);
    decisionList.append(item);
  });
  loadMeetingObsidianStatus(jobId);
}

listen(meetingCopyJsonButton, 'click', async () => {
  const minutes = currentJob && currentJob.meeting_minutes;
  if (!minutes || !Array.isArray(minutes.tasks)) return;
  const payload = JSON.stringify({
    schema: 'gurumoji.meeting.v1',
    meeting: {id: currentJob.id, source_name: currentJob.source_name},
    tasks: minutes.tasks,
  }, null, 2);
  try {
    if (!navigator.clipboard || !window.isSecureContext) throw new Error('clipboard unavailable');
    await navigator.clipboard.writeText(payload);
    setAlert(document.querySelector('#save-message'), 'タスクJSONをクリップボードへコピーしました。', false);
  } catch (_) {
    setAlert(
      document.querySelector('#save-message'),
      'クリップボードへコピーできませんでした。連携 JSON をダウンロードして外部アプリへ取り込んでください。',
      true,
    );
  }
});

listen(meetingObsidianSaveButton, 'click', async () => {
  if (!currentJobId || !currentJob?.meeting_minutes) return;
  if (currentJobDirty) {
    applyMeetingObsidianStatus({status: 'error', message: '編集内容をアプリへ保存してから、Obsidianへ保存してください。'});
    return;
  }
  const itemId = currentJobId;
  meetingObsidianSaveButton.disabled = true;
  meetingObsidianSaveButton.textContent = 'Obsidianへ保存中…';
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/meeting-obsidian`, {method: 'POST'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '会議議事録をObsidianへ保存できませんでした。');
    if (currentJobId !== itemId) return;
    applyMeetingObsidianStatus(data);
    setAlert(document.querySelector('#save-message'), '会議議事録と連携ファイルをObsidianに保存しました。', false);
  } catch (error) {
    if (currentJobId === itemId) applyMeetingObsidianStatus({status: 'error', message: error.message});
  } finally {
    meetingObsidianSaveButton.disabled = false;
  }
});

// The planned agenda next to one time-ordered account of what was discussed.
// Titles come from the AI agenda where it exists; the rest is named by theme.
function renderSessionOutline(data, outline) {
  const box = document.querySelector('#session-outline');
  const host = document.querySelector('#session-outline-content');
  const headline = document.querySelector('#session-outline-headline');
  if (!box || !host) return;
  host.replaceChildren();
  const plan = (data && data.plan) || {available: false, items: []};
  // A freshly finished transcription arrives without the joined block; show the
  // agenda it does carry rather than claiming there is no result.
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  const fallback = !data && sections.length ? {
    available: true, outline_available: true, transformer_available: false,
    rows: sections.map(section => ({
      start: section.start, end: section.end, title: section.title || '議題',
      title_source: 'outline', topics: [], segment_count: 0,
    })),
  } : null;
  const result = (data && data.result) || fallback || {available: false, rows: []};
  const rows = Array.isArray(result.rows) ? result.rows : [];
  const planItems = Array.isArray(plan.items) ? plan.items : [];
  if (headline) {
    const parts = [plan.available ? `予定 ${plan.item_count}項目` : '予定なし'];
    if (plan.available && plan.match === 'manual_topics') parts.push(`話された ${plan.discussed_count}項目`);
    parts.push(rows.length ? `結果 ${rows.length}区間` : '結果なし');
    headline.textContent = parts.join('・');
  }

  if (plan.available) {
    const section = document.createElement('section');
    section.className = 'session-outline-block';
    const head = document.createElement('h3');
    head.textContent = '予定（質問ガイド・議題）';
    section.append(head);
    if (plan.match !== 'manual_topics') {
      const note = document.createElement('p');
      note.className = 'session-outline-note';
      note.textContent = '消化状況は未照合です。「分析・可視化」のTransformerテーマ分析で決め方を「手動で定義する」にし、質問ガイドから取り込んで実行すると、項目ごとの発話数が出ます。';
      section.append(note);
    }
    const list = document.createElement('ol');
    list.className = 'session-outline-plan';
    planItems.forEach(item => {
      const entry = document.createElement('li');
      const text = document.createElement('span');
      text.className = 'session-outline-plan-text';
      text.textContent = item.text || '';
      entry.append(text);
      const statusLabels = {discussed: '話された', not_discussed: '発話の割当なし', unmatched: '未照合'};
      const status = document.createElement('span');
      status.className = `session-outline-status ${item.status || 'unmatched'}`;
      status.textContent = item.status === 'discussed'
        ? `${statusLabels.discussed}（${item.segment_count}発話・${item.speaker_count}人）`
        : statusLabels[item.status] || '未照合';
      entry.append(status);
      list.append(entry);
    });
    section.append(list);
    host.append(section);
  } else {
    const note = document.createElement('p');
    note.className = 'session-outline-note';
    note.textContent = '予定（質問ガイド・議題）は登録されていません。以下は、実際に話された結果と自動アウトラインです。予定は「会話・話者」タブの調査設計で登録できます。';
    host.append(note);
  }

  const section = document.createElement('section');
  section.className = 'session-outline-block';
  const head = document.createElement('h3');
  head.textContent = '結果（時間順）';
  section.append(head);
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'session-outline-note';
    empty.textContent = '結果はまだありません。AI仕上げのアウトライン、または「分析・可視化」のTransformerテーマ分析を実行すると、ここに時間順で並びます。';
    section.append(empty);
  } else {
    if (result.transformer_stale) {
      const stale = document.createElement('p');
      stale.className = 'session-outline-note warn';
      stale.textContent = 'テーマは実行時点の結果です。その後に本文・話者・除外が変わっています。';
      section.append(stale);
    }
    const list = document.createElement('ol');
    list.className = 'session-outline-rows';
    rows.forEach(row => {
      const entry = document.createElement('li');
      const time = document.createElement('span');
      time.className = 'session-outline-time';
      time.textContent = `${formatTime(row.start)}–${formatTime(row.end)}`;
      const body = document.createElement('div');
      const title = document.createElement('strong');
      title.textContent = row.title || '議題';
      const origin = document.createElement('span');
      origin.className = `session-outline-origin ${row.title_source}`;
      origin.textContent = row.title_source === 'outline' ? 'AI議題' : 'テーマ';
      body.append(title, origin);
      const topics = Array.isArray(row.topics) ? row.topics : [];
      if (topics.length) {
        const chips = document.createElement('div');
        chips.className = 'session-outline-topics';
        topics.forEach(topic => {
          const chip = document.createElement('span');
          chip.textContent = `${topic.label || topic.topic_id}（${topic.segment_count}）`;
          chips.append(chip);
        });
        body.append(chips);
      } else if (row.title_source === 'outline') {
        const none = document.createElement('small');
        none.textContent = result.transformer_available
          ? 'この区間にテーマ分類された発話はありません'
          : 'テーマ分析は未実行です';
        body.append(none);
      }
      entry.append(time, body);
      list.append(entry);
    });
    section.append(list);
    const foot = document.createElement('p');
    foot.className = 'session-outline-note';
    foot.textContent = '「AI議題」はAI仕上げが作った議題見出し、「テーマ」は議題のない区間をTransformerの意味クラスタから名付けた候補です。どちらも原文で確認してください。';
    section.append(foot);
    if (result.outline_available) {
      const jump = document.createElement('button');
      jump.type = 'button';
      jump.className = 'secondary-button compact-button';
      jump.textContent = '議題の要点を見る';
      jump.addEventListener('click', () => {
        setItemTab('summary');
        document.querySelector('#outline-view')?.scrollIntoView({block: 'start'});
      });
      section.append(jump);
    }
  }
  host.append(section);
  box.hidden = false;
  // Nothing to read yet: stay out of the way of the editing screen below.
  if (!plan.available && !result.available) box.open = false;
}

function renderOutline(outline) {
  const view = document.querySelector('#outline-view');
  const content = document.querySelector('#outline-content');
  content.replaceChildren();
  const sections = outline && Array.isArray(outline.sections) ? outline.sections : [];
  if (!sections.length) {
    const empty = document.createElement('p');
    empty.className = 'outline-empty';
    empty.textContent = 'AIアウトラインはまだありません。新しい文字起こしでAI仕上げを有効にすると、ここへ自動生成されます。';
    content.append(empty);
    view.hidden = false;
    return;
  }
  sections.forEach(section => {
    const row = document.createElement('section');
    row.className = 'outline-section';
    const time = document.createElement('span');
    time.className = 'outline-time';
    time.textContent = `${formatTime(section.start)}–${formatTime(section.end)}`;
    const body = document.createElement('div');
    const title = document.createElement('h4');
    title.textContent = section.title || '議題';
    const list = document.createElement('ul');
    (section.bullets || []).forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      list.append(item);
    });
    body.append(title, list);
    row.append(time, body);
    content.append(row);
  });
  view.hidden = false;
}

function segmentEmotionText(segment) {
  const emotions = segment && typeof segment.emotions === 'object' && segment.emotions ? segment.emotions : {};
  return Object.keys(emotions).sort().map(key => {
    const item = emotions[key] || {};
    const confidence = typeof item.confidence === 'number' ? ` ${item.confidence.toFixed(2)}` : '';
    return `${item.model_name || key}: ${item.label_ja || item.label || '不明'}${confidence}`;
  }).join(' / ');
}

function kushinadaEmotion(segment) {
  const data = segment && segment.emotions && segment.emotions.kushinada;
  return data && data.label ? data.label : '';
}

function renderEmotionSummary(summary) {
  const view = document.querySelector('#emotion-view');
  const content = document.querySelector('#emotion-content');
  content.replaceChildren();
  if (!summary || !summary.enabled) { view.hidden = true; return; }
  if (summary.status === 'failed') {
    const chip = document.createElement('span');
    chip.className = 'emotion-chip error';
    chip.textContent = `感情分析は未完了: ${summary.error || '詳細不明'}`;
    content.append(chip);
  } else {
    const modelNames = {};
    (summary.models || []).forEach(model => { modelNames[model.key] = model.name || model.key; });
    Object.entries(summary.label_counts || {}).forEach(([modelKey, counts]) => {
      const labels = Object.values(counts || {})
        .sort((a, b) => Number(b.count || 0) - Number(a.count || 0))
        .map(item => `${item.label_ja || item.label}: ${item.count}`);
      const chip = document.createElement('span');
      chip.className = 'emotion-chip';
      chip.textContent = `${modelNames[modelKey] || modelKey} / ${labels.join('、') || 'データなし'}`;
      content.append(chip);
    });
  }
  view.hidden = false;
}

let activePlaybackSegmentId = null;

function syncMediaPlayback(currentTime) {
  if (!currentJob || !Array.isArray(currentJob.segments)) return;
  const match = currentJob.segments.find(segment => {
    const s = Number(segment.start || 0);
    const e = Number(segment.end || 0);
    return currentTime >= s && currentTime <= e;
  });
  const matchId = match ? match.id : null;
  if (matchId === activePlaybackSegmentId) return;
  activePlaybackSegmentId = matchId;

  document.querySelectorAll('.segment.is-active-playback').forEach(el => {
    el.classList.remove('is-active-playback');
  });

  if (matchId) {
    const target = document.querySelector(`.segment[data-segment-id="${matchId}"]`);
    if (target) {
      target.classList.add('is-active-playback');
      const autoScroll = document.querySelector('#media-autoscroll');
      if (!autoScroll || autoScroll.checked) {
        target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
      }
    }
  }
}

function renderMedia(job) {
  mediaPlayerHost.replaceChildren();
  mediaPlayer = null;
  playbackStopAt = null;
  selectedSegmentId = null;
  activePlaybackSegmentId = null;
  if (!job.media_url) {
    mediaReview.hidden = true;
    return;
  }
  mediaPlayer = document.createElement(job.media_kind === 'video' ? 'video' : 'audio');
  mediaPlayer.controls = true;
  mediaPlayer.preload = 'metadata';
  mediaPlayer.src = job.media_url;
  mediaPlayer.addEventListener('timeupdate', () => {
    if (playbackStopAt !== null && mediaPlayer.currentTime >= playbackStopAt) {
      mediaPlayer.pause();
      playbackStopAt = null;
    }
    syncMediaPlayback(mediaPlayer.currentTime);
  });
  mediaPlayerHost.append(mediaPlayer);
  mediaReview.hidden = false;
}

function renderFormattingResult(result) {
  const section = document.querySelector('#formatting-result');
  const mode = document.querySelector('#formatting-result-mode');
  const metrics = document.querySelector('#formatting-result-metrics');
  const detailsHost = document.querySelector('#formatting-result-details');
  if (!section || !metrics || !detailsHost) return;
  const value = result && typeof result === 'object' ? result : null;
  section.hidden = !value || !value.summary;
  metrics.replaceChildren();
  detailsHost.replaceChildren();
  if (!value || !value.summary) return;
  if (mode) mode.textContent = `${value.mode_label || value.mode || '整形結果'}${value.manual_edit_status ? '・手動編集後' : ''}`;
  const summary = value.summary || {};
  [
    ['文字調整', summary.text_change_count, '件'],
    ['境界確認', summary.boundary_warning_count, '件'],
    ['AI文章置換', summary.recommended_replacement_count, '件'],
    ['ノイズ候補', summary.noise_candidate_count, '件'],
    ['句読点確認', summary.punctuation_warning_count, '件'],
    ['話者統合', summary.speaker_relabel_count, '発話'],
    ['AI呼び出し', summary.llm_request_count, '回']
  ].forEach(([label, count, unit]) => {
    const card = document.createElement('article');
    const caption = document.createElement('span');
    const number = document.createElement('strong');
    caption.textContent = label;
    number.textContent = `${Number(count || 0)}${unit}`;
    card.append(caption, number);
    metrics.append(card);
  });
  const appendDetails = (title, rows, describe) => {
    if (!Array.isArray(rows) || !rows.length) return;
    const details = document.createElement('details');
    const summaryElement = document.createElement('summary');
    const list = document.createElement('ul');
    summaryElement.textContent = `${title}（${rows.length}件）`;
    rows.slice(0, 50).forEach(row => {
      const item = document.createElement('li');
      item.textContent = describe(row);
      list.append(item);
    });
    details.append(summaryElement, list);
    detailsHost.append(details);
  };
  appendDetails('処理方法', value.methods, row => `${row.label}: ${row.status}`);
  appendDetails('自己紹介から抽出した話者', value.self_introductions, row => `${row.name}（${row.speaker}${row.status === 'local_candidate' ? '・ローカル抽出候補' : '・確認済み'}）`);
  appendDetails('不自然な分割の確認候補', value.boundary_warnings, row => `${row.message} 間隔 ${Number(row.gap_seconds || 0).toFixed(2)}秒`);
  appendDetails('おすすめ文章整形（Jev＋LLM）', value.recommended_reviews, row => `${row.replacement_applied ? '置換済み' : (row.llm_confirmed ? '問題確認・置換なし' : '補正不要')}［${row.effort || '中'}］— ${row.reason || row.original_text}`);
  appendDetails('ノイズ候補', value.noise_candidates, row => `${formatTime(row.start)} ${row.text} — ${row.reason}`);
  appendDetails('句読点の確認候補', value.punctuation_warnings, row => row.message || row.type || '確認してください');
  appendDetails('話者ラベルの統合', value.speaker_changes, row => `${row.from} → ${row.to}`);
}

function renderMediaBasicInfo(job) {
  const target = document.querySelector('#media-basic-info');
  if (!target) return;
  target.replaceChildren();
  const reasons = {
    ffprobe_unavailable: 'ffprobeを利用できません', file_not_found: 'ファイルが見つかりません',
    no_media_path: '元メディアの記録がありません', path_check_failed: '保存場所を確認できません',
    ffprobe_failed: 'メディア情報を取得できません', invalid_probe_json: '取得結果を読み取れません',
    metadata_unavailable: 'メタデータに値がありません'
  };
  const add = (list, label, value) => {
    const term = document.createElement('dt'), description = document.createElement('dd');
    term.textContent = label;
    description.textContent = value;
    list.append(term, description);
  };
  const general = document.createElement('dl');
  add(general, 'アプリへの取込日時', job.created_at || '不明');
  add(general, '文字起こしの最終時刻', analysisEndpointText(job.duration, job.timed_turn_count, job.missing_time_turn_count));
  target.append(general);
  if (!job.media_assets?.length) {
    const note = document.createElement('p');
    note.textContent = 'メディア情報は未記録です。起動後の記録処理が終わってから開き直してください。';
    target.append(note);
  }
  (job.media_assets || []).forEach(asset => {
    const heading = document.createElement('h4');
    heading.textContent = asset.role === 'original' ? '元ファイル' : 'アプリ保存版';
    const list = document.createElement('dl');
    add(list, '保存場所', asset.path || (asset.path_status === 'no_media_path'
      ? '不明（元メディアの記録がありません）' : '不明（保存場所の表示は許可されていません）'));
    add(list, '現在の状態', asset.path_status === 'available' ? '見つかりました' : reasons[asset.path_status] || '不明');
    const fields = [
      ['original_filename', '元ファイル名'], ['media_created_at', '収録日時'], ['file_modified_at', 'ファイル更新日時'],
      ['imported_at', 'アプリへの取込日時'], ['duration_seconds', 'メディアの長さ（秒）'], ['bytes', 'サイズ（バイト）'],
      ['container', '形式'], ['video_codec', '映像コーデック'], ['width', '幅'], ['height', '高さ'], ['fps', 'フレームレート'],
      ['audio_codec', '音声コーデック'], ['sample_rate', 'サンプリング周波数'], ['channels', 'チャンネル数'],
      ['probed_at', 'メディア情報の取得日時'], ['path_checked_at', '記録時の保存場所確認日時']
    ];
    fields.forEach(([field, label]) => add(list, label, asset[field] == null
      ? `不明（${reasons[asset.unknown_reasons?.[field]] || '値が記録されていません'}）` : String(asset[field])));
    target.append(heading, list);
  });
}

function renderResult(job) {
  if (rerunSpeakerIdentificationButton) rerunSpeakerIdentificationButton.disabled = false;
  if (speakerIdentityProvider) speakerIdentityProvider.disabled = false;
  const evidenceReturnButton = document.querySelector('#return-to-analysis-evidence');
  if (evidenceReturnButton) evidenceReturnButton.hidden = analysisEvidenceReturn?.itemId !== job.id;
  analysisCatalogLoaded = false;
  analysisCatalog = [];
  currentJob = deepCopy(job);
  currentJobBaseline = deepCopy(job);
  resultSaveConflict = false;
  deletedSegmentUndo = [];
  document.querySelector('#result-draft-recovery').hidden = true;
  document.querySelector('#undo-segment-delete').hidden = true;
  setAlert(document.querySelector('#segment-delete-status'), '');
  currentJob.segments = Array.isArray(currentJob.segments) ? currentJob.segments : [];
  currentJob.speaker_names = currentJob.speaker_names || {};
  currentJob.session_profile = currentJob.session_profile || {};
  currentJob.speaker_profiles = currentJob.speaker_profiles || {};
  currentJob.meeting_minutes = currentJob.meeting_minutes || null;
  if (speakerIdentityProvider && aiProvider && ['openai', 'google', 'lmstudio'].includes(aiProvider.value)) {
    speakerIdentityProvider.value = aiProvider.value;
  }
  if (speakerIdentityStatus) {
    const identifiedCount = Object.values(currentJob.speaker_names).filter(value => String(value || '').trim()).length;
    const registeredCount = Object.keys((job.speaker_registration || {}).created || {}).length;
    speakerIdentityStatus.textContent = identifiedCount
      ? `${identifiedCount}名の表示名を反映済みです。${registeredCount ? `${registeredCount}名を話者管理へ登録しました。` : '既存名は再実行で上書きしません。'}`
      : '話者名は未反映です。OpenAI、Gemini、またはローカルLLMで話者特定だけを実行できます。';
  }
  currentJobId = job.id;
  if (typeof resetNotationView === 'function') resetNotationView();
  if (!activeJobId) storeActiveJobId('');
  document.querySelector('#result-title').textContent = job.source_name || '確認・手動編集';
  const outputDirectory = document.querySelector('#result-output-dir');
  if (outputDirectory) {
    outputDirectory.textContent = job.output_dir ? `Gurumoji実行環境の出力フォルダー　${job.output_dir}（閲覧端末への保存はダウンロード操作で行います）` : '';
    outputDirectory.hidden = !job.output_dir;
  }
  renderDownloads(job.files);
  renderMediaBasicInfo(job);
  renderAiTokenUsage('#result-ai-usage', job.ai_usage);
  renderFormattingResult(job.formatting_result);
  renderMeetingMinutes(currentJob.meeting_minutes, job.id);
  renderOutline(job.outline);
  renderSessionOutline(job.session_outline, job.outline);
  renderEmotionSummary(job.emotion_analysis);
  renderMedia(job);
  renderSessionProfile();
  renderSpeakerEditor();
  updateSegmentFilterOptions();
  renderSegments();
  if (Object.keys((job.speaker_registration || {}).created || {}).length && !speakerRegistryDirty) {
    void loadSpeakerRegistry(true);
  }
  setAlert(document.querySelector('#save-message'), '');
  if (job.output_warning) {
    setAlert(document.querySelector('#save-message'), job.output_warning, true);
  }
  const switchingItem = renderedItemId !== String(job.id);
  renderedItemId = String(job.id);
  if (progressCard && !jobRunning) progressCard.hidden = true;
  setCurrentJobDirty(false);
  showView('item', {itemId: job.id, force: true});
  if (switchingItem) {
    setItemTab('transcript');
    window.scrollTo({top: 0, behavior: 'auto'});
  }
}

function speakerLabels() {
  return [...new Set(currentJob.segments.map(segment => segment.speaker || 'UNKNOWN'))].sort();
}

function displaySpeakerName(label) {
  const speakerLabel = String(label || 'UNKNOWN');
  const profiles = currentJob?.speaker_profiles || {}, names = currentJob?.speaker_names || {};
  const profile = Object.hasOwn(profiles, speakerLabel) ? profiles[speakerLabel] : {};
  const name = Object.hasOwn(names, speakerLabel) ? names[speakerLabel] : '';
  return profile?.display_name || name || fallbackSpeaker(speakerLabel);
}

function renderSessionProfile() {
  if (!currentJob) return;
  const profile = currentJob.session_profile || {};
  const fields = {
    '#session-type': ['session_type', 'focus_group'],
    '#session-date': ['session_date', ''],
    '#session-location': ['location', ''],
    '#session-interview-group-id': ['interview_group_id', ''],
    '#session-comparison-group': ['comparison_group', ''],
    '#session-objective': ['objective', ''],
    '#session-guide': ['moderator_guide', ''],
    '#session-conditions': ['group_conditions', ''],
    '#session-field-notes': ['field_notes', '']
  };
  Object.entries(fields).forEach(([selector, [key, fallback]]) => {
    const element = document.querySelector(selector);
    if (element) element.value = profile[key] || fallback;
  });
  const dateInput = document.querySelector('#session-date');
  const dateNote = document.querySelector('#session-date-note');
  if (dateInput) {
    dateInput.dataset.autoValue = profile.session_date_source === 'media_metadata'
      ? String(profile.session_date || '')
      : '';
  }
  if (dateNote) {
    dateNote.textContent = profile.session_date_source === 'media_metadata'
      ? '動画の撮影日時から自動入力しました。必要に応じて変更できます。'
      : '動画から取得できない場合は、手動で入力・変更できます。';
  }
  const notesDetails = document.querySelector('#session-notes-details');
  const notesSummary = document.querySelector('#session-notes-summary');
  const hasNotes = Boolean(String(profile.field_notes || '').trim());
  if (notesDetails) notesDetails.open = hasNotes;
  if (notesSummary) notesSummary.textContent = hasNotes ? '入力済み' : '未入力';
  const exportLink = document.querySelector('#conversation-speaker-export');
  if (exportLink) {
    exportLink.href = currentJob.speaker_data_url || `/api/library/${currentJobId}/speakers.csv`;
  }
}

function captureSessionProfile() {
  if (!currentJob) return {};
  const read = selector => {
    const element = document.querySelector(selector);
    return element ? element.value.trim() : '';
  };
  const sessionDate = read('#session-date');
  const dateInput = document.querySelector('#session-date');
  const sessionDateSource = sessionDate && dateInput && dateInput.dataset.autoValue === sessionDate
    ? 'media_metadata'
    : sessionDate ? 'manual' : '';
  currentJob.session_profile = {
    session_type: read('#session-type') || 'focus_group',
    session_date: sessionDate,
    session_date_source: sessionDateSource,
    location: read('#session-location'),
    interview_group_id: read('#session-interview-group-id'),
    comparison_group: read('#session-comparison-group'),
    objective: read('#session-objective'),
    moderator_guide: read('#session-guide'),
    group_conditions: read('#session-conditions'),
    field_notes: read('#session-field-notes')
  };
  return currentJob.session_profile;
}

function speakerMetrics() {
  const metrics = Object.create(null);
  let totalSeconds = 0, missingTimeCount = 0;
  const segments = currentJob.segments || [], timing = currentJob.segment_timings;
  const ids = segments.map(segment => segment.id);
  const timingBound = Array.isArray(timing) && timing.length === segments.length
    && ids.every(id => typeof id === 'string' && id) && new Set(ids).size === ids.length
    && timing.every((row, index) => row && typeof row === 'object' && !Array.isArray(row)
      && ['segment_id', 'source_start', 'source_end', 'source_time_unknown', 'valid', 'start', 'end'].every(key => Object.hasOwn(row, key))
      && row.segment_id === ids[index]);
  // Python's existing false markers include empty JSON containers. Keep this
  // finite compatibility rule local to measurement; the audio/evidence guard is separate.
  const emptyMarkerKind = value => Array.isArray(value) && value.length === 0 ? 'array'
    : value && Object.prototype.toString.call(value) === '[object Object]' && Object.keys(value).length === 0 ? 'object' : '';
  const markerKnown = value => value == null || value === false || value === 0 || value === '' || Boolean(emptyMarkerKind(value));
  const markerMatches = (left, right) => Object.is(left, right)
    || Boolean(emptyMarkerKind(left) && emptyMarkerKind(left) === emptyMarkerKind(right));
  const valid = row => row && markerKnown(row.time_unknown)
    && analysisEvidenceTimeValid({start: row.start, end: row.end})
    && row.start <= 31 * 86400 && row.end <= 31 * 86400;
  segments.forEach((segment, index) => {
    const label = segment.speaker || 'UNKNOWN';
    const data = metrics[label] || {count: 0, timedCount: 0, missingTimeCount: 0, timedSeconds: 0, seconds: null, characters: 0};
    data.count += 1;
    // Use the backend's Python-compatible conversion only while its raw binding matches.
    // A local edit or malformed/stale projection falls back to the numeric measurement guard.
    const projection = timingBound ? timing[index] : null;
    const projected = projection && {start: projection.start, end: projection.end, time_unknown: segment.time_unknown};
    const useProjection = projection?.valid === true
      && Object.is(projection.source_start, segment.start ?? null)
      && Object.is(projection.source_end, segment.end ?? null)
      && markerMatches(projection.source_time_unknown, segment.time_unknown ?? null)
      && (typeof segment.start !== 'number' || Object.is(segment.start, projection.start))
      && (typeof segment.end !== 'number' || Object.is(segment.end, projection.end)) && valid(projected);
    const measured = useProjection ? projected : segment;
    // Participation's 31-day bound does not change the separate evidence/audio seek guard.
    if (valid(measured)) {
      const duration = measured.end - measured.start;
      data.timedCount += 1;
      data.timedSeconds += duration;
      totalSeconds += duration;
    } else {
      data.missingTimeCount += 1;
      missingTimeCount += 1;
    }
    data.characters += String(segment.text || '').length;
    metrics[label] = data;
  });
  Object.values(metrics).forEach(data => {
    data.seconds = data.timedCount && Number.isFinite(data.timedSeconds) ? data.timedSeconds : null;
    data.share = missingTimeCount === 0 && Number.isFinite(totalSeconds) && totalSeconds > 0
      ? data.seconds / totalSeconds : null;
  });
  return metrics;
}

function ensureConversationSpeakerProfiles() {
  // Speaker labels are literal user data, including Object prototype property names.
  // Copy only own entries, preserving JSON keys while making subsequent writes safe.
  currentJob.speaker_names = Object.assign(Object.create(null), currentJob.speaker_names || {});
  currentJob.speaker_profiles = Object.assign(Object.create(null), currentJob.speaker_profiles || {});
  speakerLabels().forEach((label, index) => {
    currentJob.speaker_profiles[label] = {
      speaker_label: label,
      global_speaker_id: '',
      registration_status: currentJob.speaker_names[label] ? 'temporary_single_group' : 'unidentified',
      display_name: currentJob.speaker_names[label] || '',
      theme_color: speakerThemeColors[index % speakerThemeColors.length],
      session_role: 'participant',
      organization: '',
      department: '',
      job_title: '',
      attendance_status: 'attended',
      conditions: '',
      notes: '',
      ...(currentJob.speaker_profiles[label] || {})
    };
  });
}

function conversationControl(type, value, options, onChange) {
  const owner = currentJob, itemId = currentJobId;
  const apply = () => {
    if (!control.isConnected || currentJob !== owner || currentJobId !== itemId) return;
    if (onChange(control.value) !== false) setCurrentJobDirty();
  };
  const control = document.createElement(type === 'textarea' ? 'textarea' : type === 'select' ? 'select' : 'input');
  if (type === 'select') {
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value || Object.keys(options || {})[0];
    control.addEventListener('change', apply);
  } else {
    if (type !== 'textarea') control.type = type === 'color' ? 'color' : 'text';
    control.value = value || '';
    control.addEventListener('input', apply);
  }
  return control;
}

function conversationRoleControl(profile, label, metrics, index) {
  const owner = currentJob, itemId = currentJobId;
  const container = document.createElement('div');
  container.className = 'conversation-role-control';
  const select = document.createElement('select');
  Object.entries(speakerRoleLabels).forEach(([value, text]) => select.add(new Option(text, value)));
  select.value = profile.session_role || 'participant';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'この会話の役割として設定';
  const status = document.createElement('span');
  status.className = 'conversation-role-status';
  status.id = `conversation-role-status-${index}`;
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  status.textContent = ({
    __proto__: null,
    default: 'この会話では未設定（初期表示）',
    legacy_unknown: '旧データ等：設定元不明',
    registry: '話者管理から設定',
    explicit: 'この会話で明示設定'
  })[profile.session_role_source] || '旧データ等：設定元不明';
  const describe = () => {
    const displayName = (owner.speaker_profiles[label] || profile).display_name || fallbackSpeaker(label);
    const name = `${displayName}（話者ID ${label}）`;
    select.setAttribute('aria-label', `${name}の会話役割`);
    button.setAttribute('aria-label', `${name}の役割を「${speakerRoleLabels[select.value] || select.value}」としてこの会話に設定`);
  };
  for (const control of [select, button]) control.setAttribute('aria-describedby', `${status.id} conversation-role-help`);
  const applyRole = () => {
    // Detached controls and responses from an older editor cannot edit another item.
    if (!container.isConnected || currentJob !== owner || currentJobId !== itemId) return;
    // Normal save normalization replaces profiles while this editor stays mounted.
    const activeProfile = currentJob.speaker_profiles[label];
    if (!activeProfile) return;
    describe();
    if (activeProfile.session_role === select.value && activeProfile.session_role_source === 'explicit') return;
    activeProfile.session_role = select.value;
    activeProfile.session_role_source = 'explicit';
    setCurrentJobDirty();
    status.textContent = `「${speakerRoleLabels[select.value] || select.value}」をこの会話の役割に設定しました。まだ保存されていません`;
    renderSpeakerInsights(metrics);
  };
  select.addEventListener('change', applyRole);
  button.addEventListener('click', applyRole);
  describe();
  // Rename labels without dispatching a role change or certifying its provenance.
  container.refreshAccessibleName = describe;
  container.append(select, button, status);
  return container;
}

function renderSpeakerInsights(metrics) {
  const container = document.querySelector('#speaker-insights');
  if (!container) return;
  container.replaceChildren();
  const profiles = Object.values(currentJob.speaker_profiles || {});
  const sessionType = (currentJob.session_profile || {}).session_type
    || (document.querySelector('#session-type') || {}).value
    || 'focus_group';
  const add = (text, level = '') => {
    const chip = document.createElement('span');
    chip.className = `speaker-insight${level ? ` ${level}` : ''}`;
    chip.textContent = text;
    container.append(chip);
  };
  add(`話者 ${profiles.length}人`);
  const uncertainRoleCount = profiles.filter(profile => !['explicit', 'registry'].includes(profile.session_role_source)).length;
  const provisional = uncertainRoleCount > 0;
  if (provisional) add(`役割未設定・記録元不明 ${uncertainRoleCount}人（役割別人数は仮集計）`, 'warning');
  if (!Object.keys(metrics).length) add('発話なし');
  if (sessionType === 'focus_group') {
    const participants = profiles.filter(profile => profile.session_role === 'participant');
    const moderators = profiles.filter(profile => ['moderator', 'facilitator', 'assistant_moderator'].includes(profile.session_role));
    const observers = profiles.filter(profile => ['observer', 'note_taker'].includes(profile.session_role));
    add(`参加者${provisional ? '（仮）' : ''} ${participants.length}人`, !provisional && participants.length >= 6 && participants.length <= 8 ? '' : 'warning');
    add(provisional ? `司会・進行（仮） ${moderators.length}人` : moderatorCountText(moderators.length), provisional ? 'warning' : moderators.length ? '' : 'error');
    add(`観察・記録${provisional ? '（仮）' : ''} ${observers.length}人`, observers.length ? '' : 'warning');
    const participantTimeMissing = participants.some(profile => (metrics[profile.speaker_label]?.missingTimeCount || 0) > 0);
    const participantSeconds = participants.reduce((sum, profile) => (
      sum + (metrics[profile.speaker_label]?.timedSeconds || 0)
    ), 0);
    const participantTurnCount = participants.reduce((sum, profile) => sum + (metrics[profile.speaker_label]?.count || 0), 0);
    if (provisional) {
      add('役割未設定・記録元不明の話者がいるため、参加者内の割合は判定できません', 'warning');
    } else if (participants.length && !participantTurnCount) {
      add('参加者の発話なし');
    } else if (participantTimeMissing) {
      add('参加者の時刻不明があるため、発言時間の割合は判定できません', 'warning');
    } else if (participants.length && participantSeconds === 0) {
      add('参加者の総時間が0秒のため、発言時間の割合は判定できません');
    } else if (!Number.isFinite(participantSeconds)) {
      add('参加者の総時間を算出できないため、発言時間の割合は判定できません', 'warning');
    } else {
      const dominant = participants.find(profile => (
        participantSeconds > 0 && (metrics[profile.speaker_label]?.seconds || 0) / participantSeconds >= 0.5
      ));
      if (dominant) add(`${dominant.display_name || dominant.speaker_label} の発言が参加者内50%以上`, 'warning');
    }
  } else if (sessionType === 'meeting') {
    const leaders = profiles.filter(profile => ['chair', 'facilitator', 'moderator'].includes(profile.session_role));
    add(`進行・議長${provisional ? '（仮）' : ''} ${leaders.length}人`, leaders.length ? '' : 'warning');
    const decisionMakers = profiles.filter(profile => profile.session_role === 'decision_maker');
    if (decisionMakers.length) add(`意思決定者${provisional ? '（仮）' : ''} ${decisionMakers.length}人`);
  }
}

function moderatorCountText(count) {
  return `司会・進行 ${count}人`;
}

function renderSpeakerEditor({focusSpeakerLabel = '', focusField = ''} = {}) {
  speakerEditor.replaceChildren();
  if (!currentJob) return;
  const owner = currentJob, itemId = currentJobId;
  let focusTarget = null;
  captureSessionProfile();
  ensureConversationSpeakerProfiles();
  const labels = speakerLabels();
  const metrics = speakerMetrics();
  renderSpeakerInsights(metrics);
  if (!labels.length) {
    const note = document.createElement('p');
    note.className = 'segment-empty';
    note.textContent = '発話を追加すると、会話別の話者連携を設定できます。';
    speakerEditor.append(note);
    return;
  }
  const roleHelp = document.createElement('p');
  roleHelp.id = 'conversation-role-help';
  roleHelp.className = 'muted';
  roleHelp.textContent = '変更は「保存」で反映します。分析準備で記録した発話別の役割がある場合は、そちらを優先します。「登録済み」は人物の登録状態で、会話役割の設定状態とは別です。';
  speakerEditor.append(roleHelp);
  const table = document.createElement('table');
  table.className = 'conversation-speaker-sheet';
  const head = document.createElement('thead');
  head.innerHTML = '<tr><th>音声話者</th><th>表示名</th><th>テーマカラー</th><th>話者登録</th><th>グローバル話者</th><th>会話役割</th><th>組織</th><th>部署</th><th>役職</th><th>参加状態</th><th>会話固有条件</th><th>メモ</th><th>発言量</th></tr>';
  table.append(head);
  const body = document.createElement('tbody');
  labels.forEach((label, index) => {
    const profile = currentJob.speaker_profiles[label];
    const row = document.createElement('tr');
    const activeProfile = () => currentJob === owner && currentJobId === itemId && row.isConnected
      ? currentJob.speaker_profiles[label] : null;
    const fieldNames = {display_name: '表示名', theme_color: 'テーマカラー', global_speaker_id: 'グローバル話者',
      organization: '組織', department: '部署', job_title: '役職', attendance_status: '参加状態', conditions: '会話固有条件', notes: 'メモ'};
    const namedControls = [];
    const nameControl = (control, field) => {
      control.dataset.speakerLabel = label;
      control.dataset.speakerField = field;
      namedControls.push([control, field]);
      if (label === focusSpeakerLabel && field === focusField) focusTarget = control;
      return control;
    };
    const refreshNames = () => {
      const name = (owner.speaker_profiles[label] || profile).display_name || fallbackSpeaker(label);
      namedControls.forEach(([control, field]) => control.setAttribute('aria-label', `${name}（話者ID ${label}）の${fieldNames[field]}`));
      roleControl.refreshAccessibleName();
    };
    const labelCell = document.createElement('td');
    labelCell.className = 'speaker-label-cell';
    labelCell.textContent = displaySpeakerName(label);
    labelCell.title = `話者ID: ${label}`;
    row.append(labelCell);
    const displayName = conversationControl('input', profile.display_name || currentJob.speaker_names[label], null, value => {
      const targetProfile = activeProfile();
      if (!targetProfile) return false;
      targetProfile.display_name = value.trim();
      currentJob.speaker_names[label] = value.trim();
      refreshNames();
      updateSpeakerBadges();
    });
    displayName.placeholder = fallbackSpeaker(label);
    appendSheetCell(row, nameControl(displayName, 'display_name'));
    const themeColor = conversationControl('color', profile.theme_color, null, value => {
      const targetProfile = activeProfile();
      if (!targetProfile) return false;
      targetProfile.theme_color = value.toUpperCase();
      updateSpeakerBadges();
    });
    themeColor.className = 'speaker-theme-color';
    appendSheetCell(row, nameControl(themeColor, 'theme_color'));

    const globalSelect = document.createElement('select');
    globalSelect.add(new Option('未連携', ''));
    speakerRegistry.filter(record => record.active !== false).forEach(record => {
      const name = record.pseudonym || record.display_name || record.participant_code;
      const detail = [record.organization, record.job_title].filter(Boolean).join(' / ');
      globalSelect.add(new Option(detail ? `${name} — ${detail}` : name, record.id));
    });
    if (profile.global_speaker_id && !speakerRegistry.some(record => record.id === profile.global_speaker_id)) {
      globalSelect.add(new Option('削除済みの管理対象話者', profile.global_speaker_id));
    }
    globalSelect.value = profile.global_speaker_id || '';
    globalSelect.addEventListener('change', () => {
      const profile = activeProfile();
      if (!profile) return;
      const restoreFocus = document.activeElement === globalSelect;
      profile.global_speaker_id = globalSelect.value;
      const record = speakerRegistry.find(item => item.id === globalSelect.value);
      if (record) {
        profile.registration_status = 'registered';
        profile.display_name = record.pseudonym || record.display_name || record.participant_code;
        profile.session_role = record.default_role || 'participant';
        profile.session_role_source = 'registry';
        profile.organization = record.organization || '';
        profile.department = record.department || '';
        profile.job_title = record.job_title || '';
        profile.conditions = attributesToText(record.attributes);
        currentJob.speaker_names[label] = profile.display_name;
      } else {
        profile.registration_status = profile.display_name ? 'temporary_single_group' : 'unidentified';
      }
      renderSpeakerEditor(restoreFocus ? {focusSpeakerLabel: label, focusField: 'global_speaker_id'} : {});
      updateSpeakerBadges();
      setCurrentJobDirty();
    });
    const registration = document.createElement('span');
    const registrationStatus = profile.global_speaker_id
      ? 'registered'
      : (profile.registration_status || (profile.display_name ? 'temporary_single_group' : 'unidentified'));
    registration.className = `speaker-registration ${registrationStatus}`;
    registration.textContent = registrationStatus === 'registered'
      ? '登録済み'
      : registrationStatus === 'temporary_single_group'
        ? '一時話者（この会話のみ）'
        : '未特定';
    appendSheetCell(row, registration);
    appendSheetCell(row, nameControl(globalSelect, 'global_speaker_id'));
    const roleControl = conversationRoleControl(profile, label, metrics, index);
    appendSheetCell(row, roleControl);
    const addProfileControl = (type, key, options = null) => {
      const control = conversationControl(type, profile[key], options, value => {
        const targetProfile = activeProfile();
        if (!targetProfile) return false;
        targetProfile[key] = value;
      });
      appendSheetCell(row, nameControl(control, key));
    };
    ['organization', 'department', 'job_title'].forEach(key => addProfileControl('input', key));
    addProfileControl('select', 'attendance_status', attendanceLabels);
    addProfileControl('textarea', 'conditions');
    addProfileControl('textarea', 'notes');
    refreshNames();
    const metric = metrics[label];
    const metricCell = document.createElement('td');
    metricCell.className = 'speaker-metric-cell';
    const timeText = !metric.timedCount ? `時刻不明${metric.missingTimeCount}件`
      : metric.seconds === null ? '時間を算出できません'
      : metric.missingTimeCount ? `時刻あり${formatTime(metric.seconds)}（${metric.timedCount}/${metric.count}発話、時刻不明${metric.missingTimeCount}発話）`
      : formatTime(metric.seconds);
    const shareText = metric.share === null ? '割合は算出不可' : `${(metric.share * 100).toFixed(1)}%`;
    metricCell.textContent = `${metric.count}回 / ${timeText} / ${shareText}`;
    row.append(metricCell);
    body.append(row);
  });
  table.append(body);
  speakerEditor.append(table);
  if (currentJob === owner && currentJobId === itemId && focusTarget?.isConnected) focusTarget.focus();
}

[
  '#session-date', '#session-location', '#session-interview-group-id', '#session-comparison-group', '#session-objective', '#session-guide',
  '#session-conditions', '#session-field-notes'
].forEach(selector => {
  listen(document.querySelector(selector), 'input', () => {
    captureSessionProfile();
    const notesSummary = document.querySelector('#session-notes-summary');
    if (selector === '#session-field-notes' && notesSummary) {
      notesSummary.textContent = document.querySelector(selector).value.trim() ? '入力済み' : '未入力';
    }
    setCurrentJobDirty();
  });
});
listen(document.querySelector('#session-type'), 'change', () => {
  captureSessionProfile();
  if (currentJob) renderSpeakerInsights(speakerMetrics());
  setCurrentJobDirty();
});

function updateSegmentFilterOptions() {
  const select = document.querySelector('#segment-speaker-filter');
  const selected = select.value;
  select.replaceChildren(new Option('すべて', ''));
  speakerLabels().forEach(label => select.add(new Option(displaySpeakerName(label), label)));
  if ([...select.options].some(option => option.value === selected)) select.value = selected;
}

function occurrenceCount(text, keyword) {
  if (!keyword) return 0;
  return String(text || '').toLocaleLowerCase().split(keyword).length - 1;
}

function segmentReviewAgreement(segment) {
  const review = segment && segment.jev_review;
  const comparison = review && typeof review.comparison === 'object' ? review.comparison : null;
  return comparison ? String(comparison.agreement || '') : '';
}

function renderJevComparisonSummary() {
  const host = document.querySelector('#jev-comparison-summary');
  if (!host || !currentJob) return;
  const reviewed = currentJob.segments.filter(segment => segmentReviewAgreement(segment));
  host.replaceChildren();
  if (!reviewed.length) {
    host.hidden = true;
    return;
  }
  const labels = {
    both_flagged: '両方：修正が必要',
    current_only: '現行AIのみ',
    jev_only: 'Jevのみ',
    both_clear: '両方：修正不要'
  };
  const counts = Object.fromEntries(Object.keys(labels).map(key => [key, 0]));
  reviewed.forEach(segment => {
    const key = segmentReviewAgreement(segment);
    if (Object.hasOwn(counts, key)) counts[key] += 1;
  });
  const agreementCount = counts.both_flagged + counts.both_clear;
  const heading = document.createElement('div');
  heading.className = 'jev-comparison-heading';
  const text = document.createElement('div');
  const title = document.createElement('h3');
  title.textContent = '現行AI × Jev　修正要否の比較';
  const note = document.createElement('p');
  note.textContent = `判定一致 ${agreementCount} / ${reviewed.length} 発話（${Math.round(agreementCount / reviewed.length * 100)}%）。不一致は原音確認の優先候補です。`;
  text.append(title, note);
  const scope = document.createElement('span');
  scope.textContent = `${reviewed.length}発話を判定`;
  heading.append(text, scope);
  const grid = document.createElement('div');
  grid.className = 'jev-comparison-grid';
  Object.entries(labels).forEach(([key, label]) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = `jev-comparison-card ${key}`;
    const caption = document.createElement('span');
    caption.textContent = label;
    const value = document.createElement('strong');
    value.textContent = String(counts[key]);
    const unit = document.createElement('small');
    unit.textContent = '発話';
    card.append(caption, value, unit);
    card.addEventListener('click', () => {
      const filter = document.querySelector('#segment-jev-filter');
      if (filter) filter.value = key;
      renderSegments();
    });
    grid.append(card);
  });
  const caution = document.createElement('p');
  caution.className = 'jev-comparison-caution';
  caution.textContent = 'Jevは音声を聞かず、日本語の文字起こしと会話文脈だけで二択判定します。最終判断は元の音声・動画で確認してください。';
  host.append(heading, grid, caution);
  host.hidden = false;
}

function visibleSegments() {
  const keyword = document.querySelector('#segment-keyword').value.trim().toLocaleLowerCase();
  const speaker = document.querySelector('#segment-speaker-filter').value;
  const emotion = document.querySelector('#segment-emotion-filter').value;
  const jevFilter = document.querySelector('#segment-jev-filter')?.value || '';
  const sort = document.querySelector('#segment-sort').value;
  const values = currentJob.segments.filter(segment => {
    if (keyword && !String(segment.text || '').toLocaleLowerCase().includes(keyword)) return false;
    if (speaker && (segment.speaker || 'UNKNOWN') !== speaker) return false;
    const label = kushinadaEmotion(segment);
    if (emotion === 'none' && label) return false;
    if (emotion && emotion !== 'none' && label !== emotion) return false;
    if (jevFilter && segmentReviewAgreement(segment) !== jevFilter) return false;
    return true;
  });
  values.sort((a, b) => {
    if (sort === 'time_desc') return Number(b.start || 0) - Number(a.start || 0);
    if (sort === 'speaker') return String(a.speaker || '').localeCompare(String(b.speaker || ''), 'ja') || Number(a.start || 0) - Number(b.start || 0);
    if (sort === 'emotion') return kushinadaEmotion(a).localeCompare(kushinadaEmotion(b), 'ja') || Number(a.start || 0) - Number(b.start || 0);
    if (sort === 'keyword') return occurrenceCount(b.text, keyword) - occurrenceCount(a.text, keyword) || Number(a.start || 0) - Number(b.start || 0);
    return Number(a.start || 0) - Number(b.start || 0);
  });
  return values;
}

function createField(labelText, control) {
  const label = document.createElement('label');
  label.className = 'field';
  const caption = document.createElement('span');
  caption.textContent = labelText;
  label.append(caption, control);
  return label;
}

function selectSegmentForEdit(segmentId, {focus = false} = {}) {
  selectedSegmentId = segmentId;
  document.querySelectorAll('.segment').forEach(row => {
    const selected = row.dataset.segmentId === segmentId;
    row.classList.toggle('selected', selected);
    row.querySelector('.segment-edit')?.setAttribute('aria-expanded', String(selected));
    if (selected && focus) row.querySelector('textarea')?.focus();
  });
}

function undoSegmentDeletion() {
  const undo = deletedSegmentUndo.pop();
  if (!undo || undo.itemId !== currentJobId) return;
  currentJob.segments.splice(Math.min(undo.index, currentJob.segments.length), 0, undo.segment);
  selectedSegmentId = undo.segment.id;
  setCurrentJobDirty(); renderSpeakerEditor(); updateSegmentFilterOptions(); renderSegments();
  selectSegmentForEdit(undo.segment.id, {focus: true});
  setAlert(document.querySelector('#segment-delete-status'), '削除した発話を元に戻しました');
  document.querySelector('#undo-segment-delete').hidden = !deletedSegmentUndo.length;
}
listen(document.querySelector('#undo-segment-delete'), 'click', undoSegmentDeletion);

function renderSegments() {
  const active = document.activeElement;
  const focusId = active?.closest?.('.segment')?.dataset.segmentId;
  const focusField = active?.dataset.segmentField;
  const selection = typeof active?.selectionStart === 'number' ? [active.selectionStart, active.selectionEnd] : null;
  renderJevComparisonSummary();
  segmentEditor.replaceChildren();
  const values = visibleSegments();
  document.querySelector('#segment-count').textContent = `表示 ${values.length} / 全 ${currentJob.segments.length} 発話`;
  if (!values.length) {
    const empty = document.createElement('div');
    empty.className = 'segment-empty';
    empty.textContent = currentJob.segments.length ? '絞り込み条件に一致する発話はありません。' : '発話はまだありません。「発話を追加」から登録できます。';
    segmentEditor.append(empty);
    return;
  }
  values.forEach((segment, index) => {
    const row = document.createElement('article');
    row.className = `segment${segment.id === selectedSegmentId ? ' selected' : ''}`;
    row.dataset.segmentId = segment.id;
    const meta = document.createElement('div');
    meta.className = 'segment-meta';
    const time = document.createElement('span');
    time.className = 'segment-time';
    time.textContent = `${formatTime(segment.start)}–${formatTime(segment.end)}`;
    const speaker = document.createElement('span');
    speaker.className = 'segment-speaker';
    speaker.dataset.label = segment.speaker || 'UNKNOWN';
    speaker.textContent = displaySpeakerName(speaker.dataset.label);
    speaker.style.borderColor = (currentJob.speaker_profiles[speaker.dataset.label] || {}).theme_color || '';
    meta.append(time, speaker);
    const emotionText = segmentEmotionText(segment);
    if (emotionText) {
      const emotion = document.createElement('span');
      emotion.className = 'segment-emotion';
      emotion.textContent = emotionText;
      meta.append(emotion);
    }
    const agreement = segmentReviewAgreement(segment);
    if (agreement) {
      const agreementLabels = {
        both_flagged: '両方：修正必要',
        current_only: '現行AIのみ',
        jev_only: 'Jevのみ',
        both_clear: '両方：修正不要'
      };
      const badge = document.createElement('span');
      badge.className = `segment-jev-badge ${agreement}`;
      badge.textContent = agreementLabels[agreement] || 'AI判定比較';
      meta.append(badge);
    }
    const play = document.createElement('button');
    play.type = 'button';
    play.className = 'segment-play';
    play.textContent = currentJob.media_url ? '▶ 前後を再生' : '元メディアなし';
    play.disabled = !currentJob.media_url;
    play.addEventListener('click', () => playSegment(segment.id));
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'segment-edit';
    edit.textContent = '発話を編集';
    edit.setAttribute('aria-label', `${speaker.textContent} ${formatTime(segment.start)}の発話を編集`);
    edit.setAttribute('aria-expanded', String(segment.id === selectedSegmentId));
    edit.setAttribute('aria-controls', `segment-edit-body-${index}`);
    edit.addEventListener('click', () => selectSegmentForEdit(segment.id, {focus: true}));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'segment-delete';
    remove.textContent = '発話を削除';
    remove.addEventListener('click', () => {
      deletedSegmentUndo.push({itemId: currentJobId, index: currentJob.segments.findIndex(item => item.id === segment.id), segment: deepCopy(segment)});
      currentJob.segments = currentJob.segments.filter(item => item.id !== segment.id);
      if (selectedSegmentId === segment.id) selectedSegmentId = null;
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    remove.addEventListener('click', () => {
      setAlert(document.querySelector('#segment-delete-status'), '発話を削除しました。保存するまでは元に戻せます');
      const undo = document.querySelector('#undo-segment-delete');
      undo.hidden = false; undo.focus();
    });
    meta.append(edit, play, remove);

    const body = document.createElement('div');
    body.className = 'segment-body';
    body.id = `segment-edit-body-${index}`;
    const fields = document.createElement('div');
    fields.className = 'segment-fields';
    const start = document.createElement('input');
    start.dataset.segmentField = 'start';
    start.type = 'number'; start.min = '0'; start.step = '0.01'; start.value = Number(segment.start || 0).toFixed(2);
    start.addEventListener('change', () => {
      segment.start = Math.max(0, Number(start.value) || 0);
      setCurrentJobDirty();
      renderSpeakerEditor();
      renderSegments();
    });
    const end = document.createElement('input');
    end.dataset.segmentField = 'end';
    end.type = 'number'; end.min = '0'; end.step = '0.01'; end.value = Number(segment.end || 0).toFixed(2);
    end.addEventListener('change', () => {
      segment.end = Math.max(0, Number(end.value) || 0);
      setCurrentJobDirty();
      renderSpeakerEditor();
      renderSegments();
    });
    const speakerInput = document.createElement('select');
    speakerInput.dataset.segmentField = 'speaker';
    speakerLabels().forEach(label => speakerInput.add(new Option(displaySpeakerName(label), label)));
    speakerInput.value = segment.speaker || 'UNKNOWN';
    speakerInput.addEventListener('change', () => {
      segment.speaker = speakerInput.value || 'UNKNOWN';
      setCurrentJobDirty();
      renderSpeakerEditor();
      updateSegmentFilterOptions();
      renderSegments();
    });
    const emotionSelect = document.createElement('select');
    emotionSelect.dataset.segmentField = 'emotion';
    [['', '未設定'], ['neu', '平常'], ['hap', '喜び'], ['ang', '怒り'], ['sad', '悲しみ']].forEach(([value, label]) => emotionSelect.add(new Option(label, value)));
    emotionSelect.value = kushinadaEmotion(segment);
    emotionSelect.addEventListener('change', () => {
      segment.kushinada_label = emotionSelect.value;
      segment.emotions = segment.emotions || {};
      if (emotionSelect.value) {
        const labels = {neu: '平常', hap: '喜び', ang: '怒り', sad: '悲しみ'};
        segment.emotions.kushinada = {...(segment.emotions.kushinada || {}), label: emotionSelect.value, label_ja: labels[emotionSelect.value], model_name: 'くしなだ'};
      } else {
        delete segment.emotions.kushinada;
      }
      setCurrentJobDirty();
      renderSegments();
    });
    fields.append(createField('開始（秒）', start), createField('話者', speakerInput), createField('終了（秒）', end), createField('くしなだ感情', emotionSelect));
    const textarea = document.createElement('textarea');
    textarea.dataset.segmentField = 'text';
    textarea.value = segment.text || '';
    textarea.setAttribute('aria-label', `${speaker.textContent}の発話`);
    const textPreview = document.createElement('p');
    textPreview.className = 'segment-text-preview';
    textPreview.textContent = segment.text || '';
    textarea.addEventListener('input', () => {
      segment.text = textarea.value;
      textPreview.textContent = textarea.value;
      setCurrentJobDirty();
    });
    body.append(fields, textPreview, textarea);
    if (segment.ai_review && Array.isArray(segment.ai_review.fragments)) {
      const review = document.createElement('details');
      review.className = 'segment-ai-review';
      const summary = document.createElement('summary');
      summary.textContent = segment.ai_review.noise_candidate
        ? 'AI仕上げ：ノイズ候補あり（自動削除せず保持）' : 'AI仕上げ：修正理由と原文';
      const reasons = document.createElement('p');
      reasons.textContent = segment.ai_review.fragments.map(item => item.reason).filter(Boolean).join(' / ');
      const original = document.createElement('p');
      original.textContent = `校正前：${segment.ai_review.original_text || ''}`;
      const restore = document.createElement('button');
      restore.type = 'button';
      restore.textContent = '校正前の本文に戻す';
      restore.addEventListener('click', () => {
        segment.text = segment.ai_review.original_text || '';
        textarea.value = segment.text;
        textPreview.textContent = segment.text;
        setCurrentJobDirty();
      });
      review.append(summary, reasons, original, restore);
      body.append(review);
    }
    if (segment.jev_review && segment.jev_review.comparison) {
      const jevReview = document.createElement('details');
      jevReview.className = 'segment-jev-review';
      const summary = document.createElement('summary');
      const jevNeedsCorrection = segment.jev_review.decision === 'correction_needed';
      const probability = Number(segment.jev_review.correction_needed_probability);
      summary.textContent = `Jev：${jevNeedsCorrection ? '修正が必要' : '修正不要'}${Number.isFinite(probability) ? `（修正必要 ${Math.round(probability * 100)}%）` : ''}`;
      const comparison = segment.jev_review.comparison;
      const decisions = document.createElement('p');
      decisions.textContent = `現行AI：${comparison.current_ai_flagged ? '修正あり' : '修正なし'} ／ Jev：${comparison.jev_flagged ? '修正が必要' : '修正不要'}`;
      const metadata = document.createElement('p');
      const confidence = Number(segment.jev_review.confidence);
      metadata.textContent = [
        segment.jev_review.model ? `モデル ${segment.jev_review.model}` : '',
        Number.isFinite(confidence) ? `確信度 ${Math.round(confidence * 100)}%` : ''
      ].filter(Boolean).join(' ／ ');
      const original = document.createElement('p');
      original.textContent = `判定対象（校正前）：${segment.jev_review.original_text || ''}`;
      jevReview.append(summary, decisions, metadata, original);
      body.append(jevReview);
    }
    row.append(meta, body);
    row.addEventListener('click', event => {
      const isButtonOrDetails = event.target.closest('button, details, select');
      if (isButtonOrDetails) return;

      // 行またはテキストエリアをクリックしたら選択行として展開
      if (selectedSegmentId !== segment.id) {
        selectSegmentForEdit(segment.id);
      }
      // テキストエリア・入力欄自体のクリックでなければメディア再生も連動
      if (!event.target.closest('textarea, input') && currentJob.media_url) {
        playSegment(segment.id);
      }
    });
    segmentEditor.append(row);
  });
  if (focusId && focusField) {
    const row = [...segmentEditor.querySelectorAll('.segment')].find(item => item.dataset.segmentId === focusId);
    const control = row?.querySelector(`[data-segment-field="${focusField}"]`);
    if (control) { control.focus(); if (selection && control.setSelectionRange) control.setSelectionRange(...selection); }
  }
}

function updateSpeakerBadges() {
  document.querySelectorAll('.segment-speaker').forEach(badge => {
    const label = badge.dataset.label;
    badge.textContent = displaySpeakerName(label);
    badge.style.borderColor = (currentJob.speaker_profiles[label] || {}).theme_color || '';
  });
}

async function rerunSpeakerIdentification() {
  if (!currentJobId || !currentJob || !rerunSpeakerIdentificationButton
      || rerunSpeakerIdentificationButton.disabled) return;
  if (currentJobDirty) {
    setAlert(document.querySelector('#save-message'), '編集内容を保存してから話者名を再特定してください。', true);
    return;
  }
  const provider = speakerIdentityProvider ? speakerIdentityProvider.value : 'openai';
  const owner = {id: currentJobId, job: currentJob, navigation: resultRequestSequence,
    mutation: currentJobMutationGeneration};
  const ownsScreen = () => currentJobId === owner.id && resultRequestSequence === owner.navigation;
  rerunSpeakerIdentificationButton.disabled = true;
  if (speakerIdentityProvider) speakerIdentityProvider.disabled = true;
  if (speakerIdentityStatus) speakerIdentityStatus.textContent = '自己紹介候補の抽出と話者IDの再確認を実行しています…';
  setAlert(document.querySelector('#save-message'), '');
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(owner.id)}/speaker-identification`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider,
        revision_count: Number(currentJob.revision_count || 0)
      })
    });
    const data = await readJsonResponse(response);
    if (!ownsScreen() || currentJob !== owner.job) return;
    if (!response.ok) throw new Error(data.error || '話者名を再特定できませんでした。');
    if (currentJobMutationGeneration !== owner.mutation || currentJobDirty) {
      resultSaveConflict = true;
      showDraftRecovery('transcript');
      setAlert(document.querySelector('#save-message'),
        '話者の再特定は保存済みです。編集中の内容は保持しました。未保存内容を退避してから再読み込みしてください。', true);
      return;
    }
    const summary = data.speaker_identity || {};
    renderResult(data);
    owner.job = currentJob;
    owner.navigation = resultRequestSequence;
    const ambiguousCount = Object.keys(summary.ambiguous_labels || {}).length
      + Object.keys(summary.duplicate_names || {}).length;
    const repairs = summary.repairs || {};
    const repairedSegments = Math.max(0, Number(repairs.aliased_segments) || 0)
      + Math.max(0, Number(repairs.corrected_segments) || 0);
    const registeredCount = Object.keys((summary.registration || {}).created || {}).length;
    const hasChanges = Boolean(summary.applied_count || repairedSegments || registeredCount);
    const nameMessage = summary.applied_count
      ? `${summary.applied_count}名を話者IDへ反映しました。`
      : '新たに反映できる話者名はありませんでした。';
    const registrationMessage = registeredCount
      ? ` ${registeredCount}名を話者管理へ登録しました。`
      : '';
    const repairMessage = repairedSegments
      ? ` 話者ラベルの重複・断裂を${repairedSegments}発話修正しました。`
      : '';
    const ambiguityMessage = ambiguousCount
      ? ` 一意に特定できない${ambiguousCount}件は反映していません。`
      : '';
    const message = nameMessage + registrationMessage + repairMessage + ambiguityMessage;
    if (registeredCount && !speakerRegistryDirty) await loadSpeakerRegistry(true);
    if (!ownsScreen() || currentJobMutationGeneration !== owner.mutation) return;
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = message;
    setAlert(document.querySelector('#save-message'), message, !hasChanges);
  } catch (error) {
    if (!ownsScreen()) return;
    if (speakerIdentityStatus) speakerIdentityStatus.textContent = error.message;
    setAlert(document.querySelector('#save-message'), error.message, true);
  } finally {
    if (ownsScreen()) {
      rerunSpeakerIdentificationButton.disabled = false;
      if (speakerIdentityProvider) speakerIdentityProvider.disabled = false;
    }
  }
}

listen(rerunSpeakerIdentificationButton, 'click', rerunSpeakerIdentification);

['#segment-keyword', '#segment-speaker-filter', '#segment-emotion-filter', '#segment-jev-filter', '#segment-sort'].forEach(selector => {
  const element = document.querySelector(selector);
  if (!element) return;
  element.addEventListener(element.tagName === 'INPUT' ? 'input' : 'change', renderSegments);
});

listen(document.querySelector('#add-segment-button'), 'click', () => {
  if (!currentJob) return;
  const lastEnd = currentJob.segments.reduce((value, segment) => Math.max(value, Number(segment.end || 0)), 0);
  const id = self.crypto && self.crypto.randomUUID ? self.crypto.randomUUID().replaceAll('-', '') : `new_${Date.now()}`;
  selectedSegmentId = id;
  currentJob.segments.push({id, start: lastEnd, end: lastEnd + 1, speaker: speakerLabels()[0] || 'SPEAKER_00', text: '', emotions: {}, kushinada_label: ''});
  setCurrentJobDirty();
  document.querySelector('#segment-keyword').value = '';
  document.querySelector('#segment-speaker-filter').value = '';
  document.querySelector('#segment-emotion-filter').value = '';
  const jevFilter = document.querySelector('#segment-jev-filter');
  if (jevFilter) jevFilter.value = '';
  renderSpeakerEditor();
  updateSegmentFilterOptions();
  renderSegments();
  const row = document.querySelector(`[data-segment-id="${id}"] textarea`);
  if (row) { row.focus(); row.scrollIntoView({behavior: 'smooth', block: 'center'}); }
});

function playSegment(segmentId) {
  if (!mediaPlayer || !currentJob) return;
  const segment = currentJob.segments.find(item => item.id === segmentId);
  if (!segment) return;
  selectedSegmentId = segmentId;
  if (activeItemTab !== 'transcript') setItemTab('transcript');
  const context = Number(document.querySelector('#play-context').value) || 5;
  const start = Math.max(0, Number(segment.start || 0) - context);
  playbackStopAt = Number(segment.end || segment.start || 0) + context;
  document.querySelector('#media-caption').textContent = `${formatTime(segment.start)}–${formatTime(segment.end)} / ${displaySpeakerName(segment.speaker)}（前後 ${context} 秒）`;
  mediaPlayer.currentTime = start;
  const promise = mediaPlayer.play();
  if (promise) promise.catch(() => {});
  selectSegmentForEdit(segmentId);
  mediaReview.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

function adjacentSegment(direction) {
  if (!currentJob || !currentJob.segments.length) return;
  const ordered = [...currentJob.segments].sort((a, b) => Number(a.start || 0) - Number(b.start || 0));
  let index = ordered.findIndex(segment => segment.id === selectedSegmentId);
  if (index < 0) index = direction > 0 ? -1 : ordered.length;
  index = Math.max(0, Math.min(ordered.length - 1, index + direction));
  playSegment(ordered[index].id);
}

listen(document.querySelector('#previous-segment-button'), 'click', () => adjacentSegment(-1));
listen(document.querySelector('#next-segment-button'), 'click', () => adjacentSegment(1));
listen(document.querySelector('#replay-segment-button'), 'click', () => {
  const first = currentJob && [...currentJob.segments].sort((a, b) => Number(a.start || 0) - Number(b.start || 0))[0];
  if (selectedSegmentId) playSegment(selectedSegmentId);
  else if (first) playSegment(first.id);
});

listen(document.querySelector('#obsidian-finishing-button'), 'click', async () => {
  if (!currentJobId || !currentJob) return;
  const message = document.querySelector('#save-message');
  if (currentJobDirty) {
    setAlert(message, '編集内容を保存してからObsidianの作業ノートを開いてください。', true);
    return;
  }
  const button = document.querySelector('#obsidian-finishing-button');
  button.disabled = true;
  try {
    const response = await apiFetch(`/api/library/${encodeURIComponent(currentJobId)}/obsidian-finishing`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        provider: aiProvider ? aiProvider.value : 'none',
        ai_efforts: readAiEfforts(),
        jev_compare: Boolean(jevCompare && jevCompare.checked)
      })
    });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '作業ノートを開けませんでした。');
    setAlert(message, 'Gurumoji実行環境に作業ノートを用意しました。リンクは閲覧端末のObsidianで開きます。同じVaultへアクセスできる端末で利用してください。開けない場合は『ファイル・管理』から出力をダウンロードできます。Gurumojiは起動したままにしてください。 ');
    const link = document.createElement('a');
    link.href = data.uri;
    link.textContent = 'Obsidianで操作ノートを開く';
    message.append(link);
  } catch (error) {
    setAlert(message, error.message, true);
  } finally {
    button.disabled = false;
  }
});

listen(saveButton, 'click', async () => {
  if (!currentJobId || !currentJob || saveButton.disabled) return;
  const message = document.querySelector('#save-message');
  setAlert(message, '');
  saveButton.disabled = true;
  const payloadSegments = currentJob.segments.map(segment => ({
    ...segment,
    kushinada_label: segment.kushinada_label !== undefined ? segment.kushinada_label : kushinadaEmotion(segment)
  }));
  captureSessionProfile();
  ensureConversationSpeakerProfiles();
  const savedItemId = currentJobId;
  const savedJob = currentJob, savedNavigation = resultRequestSequence;
  const ownsSave = () => currentJob === savedJob && currentJobId === savedItemId
    && resultRequestSequence === savedNavigation;
  const saveGeneration = currentJobMutationGeneration;
  try {
    const response = await apiFetch(`/api/library/${savedItemId}`, {
      method: 'PUT', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        revision_count: Number(currentJob.revision_count || 0),
        source_name: currentJob.source_name,
        speaker_names: currentJob.speaker_names,
        segments: payloadSegments,
        session_profile: currentJob.session_profile,
        speaker_profiles: currentJob.speaker_profiles
      })
    });
    const data = await readJsonResponse(response);
    if (!ownsSave()) return;
    if (!response.ok) {
      const fallback = response.status === 409
        ? '別の画面または処理でデータが更新されています。未保存内容をJSONで退避してから再読み込みしてください。'
        : '保存できませんでした。';
      const revisionDetail = response.status === 409 && Number.isFinite(Number(data.current_revision))
        ? `（現在のリビジョン: ${Number(data.current_revision)}）`
        : '';
      if (response.status === 409) { resultSaveConflict = true; showDraftRecovery('transcript'); }
      throw new Error(`${response.status === 409 ? fallback : (data.error || fallback)}${revisionDetail}`);
    }
    const hasLaterChanges = currentJobId === savedItemId
      && currentJobMutationGeneration !== saveGeneration;
    if (currentJobId === savedItemId && !hasLaterChanges) {
      renderResult(data);
    } else if (currentJobId === savedItemId && currentJob) {
      currentJob.revision_count = Number(data.revision_count || currentJob.revision_count || 0);
      currentJob.files = Array.isArray(data.files) ? data.files : currentJob.files;
      renderDownloads(currentJob.files);
      setCurrentJobDirty(true, false);
    }
    const learning = data.learning_events
      ? `修正差分 ${data.learning_events} 件を、くしなだ学習用データへ追加しました。`
      : '新しい修正差分はありませんでした。';
    const warning = [data.output_warning, data.learning_warning].filter(Boolean).join(' ');
    const laterChangeNotice = hasLaterChanges
      ? ' 保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。'
      : '';
    setAlert(document.querySelector('#save-message'), `編集内容と出力ファイルを保存しました。${learning}${warning}${laterChangeNotice}`, Boolean(warning || hasLaterChanges));
    loadTrainingStatus();
  } catch (error) {
    if (!ownsSave()) return;
    setCurrentJobDirty(true, false);
    setAlert(message, error.message, true);
  } finally {
    if (ownsSave()) saveButton.disabled = false;
  }
});

listen(deleteRecordButton, 'click', () => {
  if (currentJobId && currentJob) deleteLibraryItem(currentJobId, currentJob.source_name);
});

resultContextButtons.forEach(button => {
  listen(button, 'click', () => openResultDestination(button.dataset.resultDestination));
});
listen(resultAnalysisButton, 'click', () => openAnalysisForItem(currentJobId));
listen(document.querySelector('#return-to-analysis-evidence'), 'click', returnToAnalysisEvidence);
listen(newButton, 'click', () => showView('library'));

function analysisElement(tagName, className = '', textValue = '') {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (textValue !== undefined && textValue !== null && textValue !== '') {
    element.textContent = String(textValue);
  }
  return element;
}

function safeAnalysisColor(value, fallback = '#1C6B50') {
  const color = String(value || '').toUpperCase();
  return /^#[0-9A-F]{6}$/.test(color) ? color : fallback;
}

function boundedAnalysisPercent(value) {
  const number = Number(value);
  return Number.isFinite(number) ? Math.min(100, Math.max(0, number)) : 0;
}

function analysisNumberText(value, digits = 1, suffix = '') {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(digits)}${suffix}` : '—';
}

function analysisEndpointText(value, timed, missing) {
  if (value === null || value === undefined || value === '' || typeof value === 'boolean'
      || !Number.isFinite(Number(value)) || Number(value) < 0) {
    return missing > 0 ? `時刻不明${missing}発話` : '時刻不明';
  }
  const coverage = Number.isInteger(timed) && Number.isInteger(missing)
    ? `（時刻あり${timed}/${timed + missing}発話${missing ? `、時刻不明${missing}発話` : ''}）` : '';
  return `${formatTime(value)}${coverage}`;
}

function analysisObservedTimeText(metric, key = 'speaking_seconds', formatter = formatTime) {
  const value = metric?.[key];
  const missing = Number.isInteger(metric?.missing_time_turn_count) ? metric.missing_time_turn_count : null;
  const timed = Number.isInteger(metric?.timed_turn_count) ? metric.timed_turn_count : null;
  if (value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) || Number(value) < 0) {
    if (metric?.role_aggregation_status === 'mixed') return '役割混在で算出不可';
    return missing > 0 ? `時刻不明${missing}発話` : '時刻不明';
  }
  const text = formatter(value);
  return missing > 0 && timed !== null
    ? `時刻あり${text}（${timed}/${timed + missing}発話、時刻不明${missing}発話）` : text;
}

function analysisExportLink(label, dataset, className = 'analysis-export-link') {
  const exports = analysisState.data && analysisState.data.exports;
  const href = (exports && exports[dataset]) || (
    dataset === 'report' && analysisState.itemId
      ? `/api/library/${encodeURIComponent(analysisState.itemId)}/analysis/export.md`
      : ''
  );
  if (!href || !String(href).startsWith('/api/')) return null;
  const link = analysisElement('a', className, label);
  link.href = href;
  link.download = '';
  link.setAttribute('aria-label', `${label}をダウンロード`);
  return link;
}

function analysisExportDirectory(title, classification, datasets) {
  const section = analysisCardPanel(title, classification, '', true);
  const links = analysisElement('div', 'analysis-export-directory');
  datasets.forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-data-export');
    if (link) links.append(link);
  });
  if (links.childNodes.length) section.body.append(links);
  else section.body.append(analysisElement('p', 'analysis-no-data', '出力できる集計データがありません。'));
  return section.panel;
}

function setAnalysisDirty(dirty, trackMutation = true) {
  analysisState.dirty = Boolean(dirty);
  if (analysisState.dirty && trackMutation) analysisMutationGeneration += 1;
  document.querySelectorAll('[data-analysis-save]').forEach(button => {
    button.disabled = !analysisState.dirty || analysisSaveInProgress;
    button.textContent = analysisSaveInProgress
      ? '保存中…'
      : analysisState.dirty ? '設定とコードを保存' : '保存済み';
  });
  document.querySelectorAll('[data-analysis-save-state]').forEach(element => {
    element.textContent = analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです';
    element.classList.toggle('unsaved', analysisState.dirty);
  });
  const sideStatus = document.querySelector('#analysis-desktop-side-status');
  if (sideStatus) {
    sideStatus.classList.toggle('unsaved', analysisState.dirty);
    sideStatus.textContent = analysisState.dirty
      ? '設定・コードに未保存の変更があります'
      : analysisState.data ? '保存済みの分析結果を表示中' : '';
  }
  refreshInsightControls();
  refreshAnalysisStorage();
}

function setAnalysisLoading(loading) {
  const loadingView = document.querySelector('#analysis-loading');
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (loadingView) loadingView.hidden = !loading;
  if (shell) shell.hidden = loading || !analysisState.data;
  if (empty) empty.hidden = loading || Boolean(analysisState.data);
  if (analysisItemSelect) analysisItemSelect.disabled = loading;
}

function updateAnalysisTarget() {
  const selected = analysisCatalog.find(item => item.id === analysisState.itemId);
  const name = document.querySelector('#analysis-target-name');
  const meta = document.querySelector('#analysis-target-meta');
  if (name) name.textContent = selected ? selected.source_name : '未選択';
  const openButton = document.querySelector('#analysis-open-item-button');
  if (openButton) openButton.hidden = !selected;
  if (meta) {
    meta.textContent = selected
      ? `発話 ${selected.segment_count || 0}件 / 最終時刻 ${analysisEndpointText(selected.duration, selected.timed_turn_count, selected.missing_time_turn_count)} / 更新 ${formatDate(selected.updated_at)}`
      : '処理済みデータを選択してください';
  }
  const exportLink = document.querySelector('#analysis-json-export');
  const jsonHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.json;
  if (exportLink) {
    exportLink.hidden = !jsonHref;
    if (jsonHref && String(jsonHref).startsWith('/api/')) exportLink.href = jsonHref;
  }
  const xlsxLink = document.querySelector('#analysis-xlsx-export');
  const xlsxHref = analysisState.data && analysisState.data.exports && analysisState.data.exports.xlsx;
  if (xlsxLink) {
    xlsxLink.hidden = !xlsxHref;
    if (xlsxHref && String(xlsxHref).startsWith('/api/')) xlsxLink.href = xlsxHref;
  }
}

async function loadAnalysisCatalog(force = false) {
  if (analysisCatalogLoaded && !force) {
    if (analysisState.itemId && !analysisState.data) loadAnalysisItem(analysisState.itemId);
    return;
  }
  setAlert(document.querySelector('#analysis-message'), '');
  if (analysisItemSelect) {
    analysisItemSelect.disabled = true;
    analysisItemSelect.replaceChildren(new Option('処理済みデータを読み込んでいます…', ''));
  }
  try {
    const response = await apiFetch('/api/library?sort=updated_desc', {cache: 'no-store'});
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error || '分析対象を取得できませんでした。');
    analysisCatalog = Array.isArray(data.items) ? data.items : [];
    analysisCatalogLoaded = true;
    if (analysisItemSelect) {
      analysisItemSelect.replaceChildren();
      if (!analysisCatalog.length) {
        analysisItemSelect.add(new Option('分析できる処理済みデータがありません', ''));
      } else {
        analysisCatalog.forEach(item => {
          const label = `${item.source_name}（発話 ${item.segment_count || 0}件）`;
          analysisItemSelect.add(new Option(label, item.id));
        });
      }
    }
    const currentExists = analysisCatalog.some(item => item.id === analysisState.itemId);
    const resultExists = analysisCatalog.some(item => item.id === currentJobId);
    const linkedItem = !analysisLinkedItemApplied ? new URLSearchParams(location.search).get('item') : '';
    analysisLinkedItemApplied = true;
    const nextId = linkedItem || (currentExists
      ? analysisState.itemId
      : resultExists ? currentJobId : (analysisCatalog[0] || {}).id || '');
    if (analysisItemSelect) analysisItemSelect.value = nextId;
    if (nextId) await loadAnalysisItem(nextId, {discardDirty: force});
    else {
      analysisState.itemId = '';
      analysisState.data = null;
      updateAnalysisTarget();
      setAnalysisLoading(false);
    }
  } catch (error) {
    setAlert(document.querySelector('#analysis-message'), error.message, true);
    analysisState.data = null;
    setAnalysisLoading(false);
  } finally {
    if (analysisItemSelect) analysisItemSelect.disabled = false;
  }
}

async function loadAnalysisItem(itemId, {discardDirty = false, execute = false} = {}) {
  const nextId = String(itemId || '');
  if (!nextId) return;
  if (!discardDirty && hasUnsavedAnalysisChanges()) {
    const leave = window.confirm('分析設定・手動コード・準備記録に未保存の変更があります。破棄してデータを読み込みますか？');
    if (!leave) {
      if (analysisItemSelect) analysisItemSelect.value = analysisState.itemId;
      return;
    }
  }
  const closedFixedViewer = typeof closeFixedAnalysisViewer === 'function' && closeFixedAnalysisViewer();
  const closedAnalysisDialog = typeof closeAnalysisExecutionDialog === 'function' && closeAnalysisExecutionDialog();
  if ((closedFixedViewer || closedAnalysisDialog) && analysisItemSelect?.isConnected && !analysisItemSelect.closest('[hidden]')) analysisItemSelect.focus();
  if (analysisRequestController) analysisRequestController.abort();
  analysisRequestController = new AbortController();
  analysisNavigationGeneration += 1;
  // The former view's request may finish, but it no longer owns these controls.
  analysisSaveOwner = null;
  analysisSaveInProgress = false;
  analysisTermRunRequested = false;
  const requestId = ++analysisRequestSequence;
  const executionView = document.querySelector('#analysis-execution-view');
  if (executionView) executionView.hidden = true;
  analysisState.itemId = nextId;
  analysisState.data = null;
  if (analysisItemSelect) analysisItemSelect.value = nextId;
  updateAnalysisTarget();
  if (analysisCard && !analysisCard.hidden) syncRouteHash(routeHash('analysis', nextId), {replace: true});
  setAnalysisLoading(true);
  setAlert(document.querySelector('#analysis-message'), '');
  try {
    const query = execute ? '?execute=1' : '';
    const response = await apiFetch(`/api/library/${encodeURIComponent(nextId)}/analysis${query}`, {
      cache: 'no-store', signal: analysisRequestController.signal
    });
    const payload = await readJsonResponse(response);
    if (requestId !== analysisRequestSequence) return;
    if (!response.ok) throw new Error(payload.error || '分析データを取得できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisState.data = data;
    invalidateAnalysisMethodOverview();
    analysisState.config = deepCopy(data.config || {});
    analysisState.annotations = deepCopy(data.annotations || {});
    preparationDraft = null;
    preparationDirty = false;
    analysisState.segmentQuery = '';
    analysisState.annotatedOnly = false;
    analysisState.speakerAttributeFilter = '';
    analysisState.selectedSpeaker = '';
    setAnalysisDirty(false);
    renderAnalysisWorkspace();
    onContentAnalysisLoaded();
  } catch (error) {
    if (error.name === 'AbortError') return;
    if (requestId !== analysisRequestSequence) return;
    analysisState.data = null;
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    if (requestId === analysisRequestSequence) setAnalysisLoading(false);
  }
}

function setAnalysisMode(mode) {
  analysisState.mode = ['manual', 'methods'].includes(mode) ? mode : 'automatic';
  renderAnalysisWorkspace();
}

function analysisModeContent(compact) {
  if (analysisState.mode === 'manual') return renderManualAnalysis(compact);
  if (analysisState.mode === 'methods') return renderMethodAnalysis(compact);
  return renderAutomaticAnalysis(compact);
}

function renderAnalysisWorkspace() {
  if (!analysisState.data) return;
  const shell = document.querySelector('#analysis-shell');
  const empty = document.querySelector('#analysis-empty');
  if (analysisState.data.executed === false && analysisState.mode === 'automatic') {
    if (shell) shell.hidden = true;
    if (empty) {
      empty.hidden = false;
      const title = empty.querySelector('strong');
      const desc = empty.querySelector('p');
      if (title) title.textContent = '分析はまだ実行されていません';
      if (desc) desc.textContent = '右上の［分析を実行］ボタンを押すと、発話量・会話構造・形態素・共起・統計検定の分析を開始します。';
      let history = empty.querySelector('.analysis-empty-history');
      if (!history) {
        history = analysisElement('div', 'analysis-empty-history');
        empty.append(history);
      }
      history.replaceChildren(buildAnalysisStorage({readOnly: true}));
    }
    setAnalysisDirty(analysisState.dirty, false);
    refreshAnalysisStorage();
    return;
  }
  document.querySelectorAll('[data-analysis-mode]').forEach(button => {
    const active = button.dataset.analysisMode === analysisState.mode;
    button.classList.toggle('active', active);
    button.setAttribute('aria-pressed', String(active));
  });
  updateAnalysisTarget();
  if (analysisDesktopContent) {
    analysisDesktopContent.replaceChildren();
    analysisDesktopContent.append(analysisModeContent(false));
  }
  if (analysisMobileContent) {
    analysisMobileContent.replaceChildren();
    analysisMobileContent.append(analysisModeContent(true));
  }
  if (shell) shell.hidden = false;
  if (empty) empty.hidden = true;
  setAnalysisDirty(analysisState.dirty, false);
  renderKwicResults();
  refreshInsightControls();
  refreshAnalysisStorage();
  restoreAnalysisEvidencePosition();
  scheduleAnalysisNavigationSync();
  if (!analysisInitialSectionApplied && requestedAnalysisSection) {
    analysisInitialSectionApplied = true;
    requestAnimationFrame(() => {
      const content = window.matchMedia('(max-width: 959px)').matches
        ? analysisMobileContent : analysisDesktopContent;
      const target = content && content.querySelector(`[data-analysis-anchor="${requestedAnalysisSection}"]`);
      const jump = content && content.querySelector(`[data-analysis-jump="${requestedAnalysisSection}"]`);
      selectAnalysisPage(requestedAnalysisSection);
      if (jump) {
        content.querySelectorAll('[data-analysis-jump]').forEach(button => button.classList.toggle('active', button === jump));
      }
      if (target) target.scrollIntoView({block: 'start'});
    });
  }
}

// Shared analysis charts and navigation are in analysis-visualizations.js.

function appendResearchAnalysis(grid, compact) {
  const research = (analysisState.data && analysisState.data.research) || {};
  const linguistics = research.linguistics || {};
  const statistics = research.statistics || {};
  const engine = linguistics.engine || {};
  const coverage = linguistics.coverage || {};

  const morphologyPanel = analysisCardPanel('使われた言葉の種類（形態素・品詞）', 'automatic', 'morphemes', true, 'morphology');
  const engineNotice = analysisElement('div', `analysis-engine-notice ${engine.status || 'fallback'}`);
  engineNotice.append(
    analysisElement('strong', '', `${engine.morphology || '解析器未確認'} / ${engine.syntax || '構文解析未確認'}`),
    analysisElement('p', '', engine.message || '解析状態を確認できませんでした。')
  );
  morphologyPanel.body.append(engineNotice);
  const morphologyMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(morphologyMetrics, '形態素', `${coverage.token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '内容語', `${coverage.content_token_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '文', `${coverage.sentence_count || 0}件`);
  appendAnalysisMetric(morphologyMetrics, '係り受け', `${coverage.dependency_count || 0}件`);
  morphologyPanel.body.append(morphologyMetrics);
  const posRows = Array.isArray(linguistics.pos_frequency) ? linguistics.pos_frequency : [];
  const maxPos = Math.max(1, ...posRows.map(item => Number(item.count) || 0));
  posRows.slice(0, compact ? 7 : 12).forEach(item => appendAnalysisBar(
    morphologyPanel.body,
    [item.upos, item.pos_detail].filter(Boolean).join(' / '),
    100 * (Number(item.count) || 0) / maxPos,
    `${item.count || 0}件 / ${analysisNumberText(item.percent, 1, '%')}`,
    '#2F80ED'
  ));
  const morphologyExports = analysisElement('div', 'analysis-inline-exports');
  [
    ['dependencies', '係り受けCSV'],
    ['pos_frequency', '品詞頻度CSV']
  ].forEach(([dataset, label]) => {
    const link = analysisExportLink(label, dataset, 'analysis-inline-export');
    if (link) morphologyExports.append(link);
  });
  morphologyPanel.body.append(morphologyExports);
  grid.append(morphologyPanel.panel);

  const termsPanel = analysisCardPanel('よく使われた言葉（TF・DF）', 'automatic', 'term_frequency', false, 'lexical_frequency');
  const terms = Array.isArray(linguistics.term_frequency) ? linguistics.term_frequency : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    '#6C8B3C'
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', '内容語を抽出できませんでした。解析器の状態と原文を確認してください。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', 'TFは総出現回数、DFはその語を含む発話数です。頻度は重要性を意味しません。'));
  grid.append(termsPanel.panel);

  const cooccurrencePanel = analysisCardPanel('一緒に使われる言葉のつながり（共起）', 'automatic', 'cooccurrence', true, 'cooccurrence');
  const cooccurrence = Array.isArray(linguistics.cooccurrence) ? linguistics.cooccurrence : [];
  if (cooccurrence.length) {
    cooccurrencePanel.body.append(buildAnalysisCooccurrenceExplorer(cooccurrence));
  } else {
    cooccurrencePanel.body.append(analysisElement('p', 'analysis-no-data', `同じ発話で${coverage.cooccurrence_min_count || 2}回以上共起する語の組み合わせがありません。`));
  }
  cooccurrencePanel.body.append(analysisElement('p', 'analysis-caption', `発話を文書単位とし、上位${coverage.cooccurrence_top_terms || 60}語からJaccard係数を計算しています。関係の意味は原文で確認してください。`));
  grid.append(cooccurrencePanel.panel);

  const dependencies = Array.isArray(linguistics.dependency_preview) ? linguistics.dependency_preview : [];
  const syntaxPanel = analysisCardPanel('文章内の言葉のつながり（係り受け）', 'automatic', 'dependencies', true, 'syntax');
  if (dependencies.length) {
    syntaxPanel.body.append(buildAnalysisDependencyExplorer(dependencies, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '係り受けの表データを確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['発話', '語', '原形', '品詞', '関係', '係り先'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    dependencies.slice(0, compact ? 12 : 30).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.segment_id),
        analysisElement('td', '', item.surface),
        analysisElement('td', '', item.lemma),
        analysisElement('td', '', item.upos),
        analysisElement('td', '', item.dependency),
        analysisElement('td', '', item.head_token_id ? `${item.head_surface} (#${item.head_token_id})` : 'ROOT')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    syntaxPanel.body.append(details);
  } else {
    syntaxPanel.body.append(analysisElement('p', 'analysis-no-data', '係り受けデータがありません。GiNZAとja-ginzaの導入状態を確認してください。'));
  }
  grid.append(syntaxPanel.panel);

  grid.append(analysisSectionHeading(
    'statistics', '03 / STATISTICS', '統計で比較する',
    '発話単位の分布、変数間の関連、群間差を順に確認します。p値だけでなく効果量・標本数・前提条件も併記します。'
  ));

  const correlations = Array.isArray(statistics.correlations) ? statistics.correlations : [];
  const computedCorrelations = correlations.filter(item => item.status === 'computed');
  const correlationPanel = analysisCardPanel('指標どうしの関係（相関）', 'automatic', 'correlations', true, 'correlation');
  if (computedCorrelations.length) {
    correlationPanel.body.append(buildAnalysisCorrelationExplorer(correlations));
  } else {
    correlationPanel.body.append(analysisElement('p', 'analysis-no-data', '相関を計算できる変数または標本数が不足しています。'));
  }
  grid.append(correlationPanel.panel);

  const descriptives = (Array.isArray(statistics.descriptives) ? statistics.descriptives : [])
    .filter(item => item.scope === 'overall');
  const statsPanel = analysisCardPanel('会話データの基本統計', 'automatic', 'descriptives', true, 'descriptive_statistics');
  if (descriptives.length) {
    statsPanel.body.append(buildAnalysisDescriptiveChart(descriptives));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '記述統計の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['変数', '分析単位・測定単位', 'N', '欠測', '平均', '標準偏差', '中央値', '最小', '最大'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    descriptives.forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.label || item.variable),
        analysisElement('td', '', `${item.analysis_unit || statistics.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
        analysisElement('td', '', analysisNumberText(item.mean, 3)),
        analysisElement('td', '', analysisNumberText(item.standard_deviation, 3)),
        analysisElement('td', '', analysisNumberText(item.median, 3)),
        analysisElement('td', '', analysisNumberText(item.minimum, 3)),
        analysisElement('td', '', analysisNumberText(item.maximum, 3))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    statsPanel.body.append(details);
  } else statsPanel.body.append(analysisElement('p', 'analysis-no-data', '記述統計を計算できる発話がありません。'));
  statsPanel.body.append(analysisElement('p', 'analysis-caption', `分析単位: ${statistics.analysis_unit || '発話'} / 比較軸: ${statistics.group_variable === 'role' ? '役割' : '話者'}。欠損値は変数ごとに除外します。`));
  grid.append(statsPanel.panel);

  const frequencies = Array.isArray(statistics.frequencies) ? statistics.frequencies : [];
  const frequencyPanel = analysisCardPanel('カテゴリ別の件数と割合', 'automatic', 'frequencies', true, 'descriptive_statistics');
  if (frequencies.length) {
    frequencyPanel.body.append(buildAnalysisFrequencyExplorer(frequencies, compact));
  } else {
    frequencyPanel.body.append(analysisElement('p', 'analysis-no-data', '割合を可視化できるカテゴリデータがありません。'));
  }
  grid.append(frequencyPanel.panel);

  const tests = Array.isArray(statistics.tests) ? statistics.tests : [];
  const crosstabs = Array.isArray(statistics.crosstabs) ? statistics.crosstabs : [];
  const selectedTerms = Array.isArray(statistics.selected_terms) ? statistics.selected_terms : [];
  const selectedTermPanel = analysisCardPanel('手動選択単語のクロス集計＋カイ二乗検定', 'configured', 'crosstabs', true, 'group_statistics');
  if (selectedTerms.length) {
    selectedTerms.slice(0, compact ? 8 : 20).forEach(term => {
      const columnVariable = `selected_term:${term}`;
      const rows = crosstabs.filter(item => item.column_variable === columnVariable);
      const test = tests.find(item => item.family === 'クロス集計' && (item.term === term || item.outcome === rows[0]?.table_id || item.outcome === columnVariable));
      const matchMode = rows[0]?.match_mode || statistics.crosstab_match_mode || 'normalized';
      const article = analysisElement('article', 'analysis-selected-term-result');
      article.append(analysisElement('h4', '', `「${term}」 × ${statistics.group_variable === 'role' ? '役割' : '話者'} / ${analysisMatchModeLabel(matchMode)}`));
      const evidence = analysisElement('button', 'secondary-button', '同じ一致条件で文脈を確認');
      evidence.type = 'button';
      evidence.addEventListener('click', () => {
        selectAnalysisPage('content');
        if (typeof runKwicSearch === 'function') runKwicSearch({query: term, matchMode, offset: 0});
      });
      article.append(evidence);
      if (rows.length) {
        const wrap = analysisElement('div', 'analysis-table-wrap');
        const table = analysisElement('table', 'analysis-table');
        const head = analysisElement('thead');
        const headRow = analysisElement('tr');
        ['比較群', '出現', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
        head.append(headRow);
        const body = analysisElement('tbody');
        rows.forEach(item => {
          const row = analysisElement('tr');
          row.append(
            analysisElement('td', '', item.row_value),
            analysisElement('td', '', item.column_value),
            analysisElement('td', '', item.count || 0),
            analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
            analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
          );
          body.append(row);
        });
        table.append(head, body);
        wrap.append(table);
        article.append(wrap);
      }
      if (test && test.status === 'computed') {
        article.append(analysisElement(
          'p',
          'analysis-term-test-summary',
          `Pearson χ²(${test.df1}) = ${analysisNumberText(test.statistic, 3)}, ${analysisPValueText(test.p_value)}, Cramér's V = ${analysisNumberText(test.effect_size, 3)}, N = ${test.n || 0}`
        ));
      } else {
        article.append(analysisElement('p', 'analysis-term-test-summary unavailable', '比較群または「あり／なし」の一方が不足しているため検定は未計算です。'));
      }
      selectedTermPanel.body.append(article);
    });
  } else {
    selectedTermPanel.body.append(analysisElement('p', 'analysis-no-data', '「設定・手動」画面で単語を選び、検定を実行してください。'));
  }
  selectedTermPanel.body.append(analysisElement('p', 'analysis-caption', '発話単位の探索的検定です。同じ話者の発話は独立でない可能性があり、多重検定補正も行っていません。'));
  grid.append(selectedTermPanel.panel);

  const testsPanel = analysisCardPanel('グループ間の違いと効果の大きさ', 'automatic', 'statistical_tests', true, 'group_statistics');
  const computedTests = tests.filter(item => item.status === 'computed');
  if (computedTests.length) {
    testsPanel.body.append(buildAnalysisEffectChart(computedTests, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', '統計検定の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table analysis-stat-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['検定', '対象', '分析単位・測定単位', 'N', '欠測', '統計量', 'p値（未補正）', '効果量'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    computedTests.slice(0, compact ? 10 : 24).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.test),
        analysisElement('td', '', item.outcome_label || item.outcome),
        analysisElement('td', '', `${item.analysis_unit || '発話'} / ${item.unit || '—'}`),
        analysisElement('td', '', item.n || 0),
        analysisElement('td', '', item.missing ?? '—'),
        analysisElement('td', '', analysisNumberText(item.statistic, 3)),
        analysisElement('td', '', analysisPValueText(item.p_value)),
        analysisElement('td', '', item.effect_name ? `${item.effect_name} = ${analysisNumberText(item.effect_size, 3)}` : '—')
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    testsPanel.body.append(details);
  } else testsPanel.body.append(analysisElement('p', 'analysis-no-data', '比較群または標本数が不足しているため、推測統計を計算していません。'));
  const unavailableCount = tests.filter(item => item.status !== 'computed').length;
  testsPanel.body.append(analysisElement('p', 'analysis-caption', `発話単位の探索的検定・p値は多重検定未補正です。同じ話者の発話は独立ではない可能性があります。p値だけで結論を出さず、効果量・標本数・欠測と前提条件を確認してください。未計算 ${unavailableCount}件。`));
  grid.append(testsPanel.panel);

  const crosstabsPanel = analysisCardPanel('項目の組み合わせ比較（クロス集計）', 'automatic', 'crosstabs', true, 'group_statistics');
  if (crosstabs.length) {
    crosstabsPanel.body.append(buildAnalysisCrosstabExplorer(crosstabs, compact));
    const details = analysisElement('details', 'analysis-table-details');
    details.append(analysisElement('summary', '', 'クロス集計の数値表を確認'));
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['表', '行', '列', '度数', '行%', '列%'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    crosstabs.slice(0, compact ? 16 : 40).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.table_label),
        analysisElement('td', '', item.row_value),
        analysisElement('td', '', item.column_value),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.row_percent, 1, '%')),
        analysisElement('td', '', analysisNumberText(item.column_percent, 1, '%'))
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    details.append(wrap);
    crosstabsPanel.body.append(details);
  } else crosstabsPanel.body.append(analysisElement('p', 'analysis-no-data', 'クロス集計できるデータがありません。'));
  grid.append(crosstabsPanel.panel);

  grid.append(analysisSectionHeading(
    'exports', '04 / OUTPUT & REVIEW', '出力して検証する',
    '標準出力のExcel、再分析用CSV、手法と限界をまとめています。論文利用前に原文・欠損・解析器の状態を確認してください。'
  ));

  const rowLimits = (analysisState.data?.research || {}).row_limits || {};
  const truncatedRows = Object.entries(rowLimits).filter(([, value]) => value.truncated);
  if (truncatedRows.length) grid.append(analysisElement('p', 'analysis-limit-note', `画面用プレビュー: ${truncatedRows.map(([key, value]) => `${key} ${value.returned_rows}/${value.total_rows}行`).join('、')}。全件はCSV/Excel出力で確認してください。`));
  if (coverage.cooccurrence_truncated) grid.append(analysisElement('p', 'analysis-limit-note', `共起の候補集合: 上位${coverage.cooccurrence_top_terms}語 / 最小${coverage.cooccurrence_min_count}発話。共起行 ${coverage.cooccurrence_returned_rows}/${coverage.cooccurrence_total_rows}件。候補制限により会話全体の全関係を表しません。`));
  grid.append(analysisExportDirectory('研究分析データの出力', 'automatic', [
    ['xlsx', 'Excelブック（標準出力）'],
    ['transformer_topics', 'Transformerテーマ CSV'],
    ['transformer_assignments', 'Transformer発話分類 CSV'],
    ['transformer_speakers', 'Transformer話者比較 CSV'],
    ['transformer_timeline', 'Transformer時間推移 CSV'],
    ['transformer_outliers', 'Transformer例外候補 CSV'],
    ['segments_all', '発話データ CSV'],
    ['morphemes', '形態素 CSV'],
    ['dependencies', '構文・係り受け CSV'],
    ['pos_frequency', '品詞頻度 CSV'],
    ['term_frequency', '語彙頻度 CSV'],
    ['cooccurrence', '共起 CSV'],
    ['descriptives', '記述統計 CSV'],
    ['frequencies', '度数分布 CSV'],
    ['crosstabs', 'クロス集計 CSV'],
    ['statistical_tests', '統計検定 CSV'],
    ['correlations', '相関 CSV'],
    ['analysis_methods', '分析手法・出典 CSV']
  ]));

  const methodsPanel = analysisCardPanel('分析方法と結果を見るときの注意', 'automatic', 'analysis_methods', true);
  const methods = Array.isArray(research.methods) ? research.methods : [];
  methods.forEach(item => {
    const article = analysisElement('article', 'analysis-method-item');
    article.append(
      analysisElement('strong', '', `${item.category}: ${item.method}`),
      analysisElement('p', '', `${item.engine || '内蔵'} ${item.engine_version || ''} / ${item.description || ''}`)
    );
    if (item.source_url && String(item.source_url).startsWith('https://')) {
      const link = analysisElement('a', '', item.source_title || '公式資料');
      link.href = item.source_url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      article.append(link);
    }
    methodsPanel.body.append(article);
  });
  const limitations = Array.isArray(research.limitations) ? research.limitations : [];
  if (limitations.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '論文利用前に確認する限界'));
    const list = analysisElement('ul');
    limitations.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    methodsPanel.body.append(details);
  }
  grid.append(methodsPanel.panel);
}

function buildAnalysisScopeSwitch() {
  const switcher = analysisElement('section', 'analysis-scope-switch');
  switcher.setAttribute('aria-label', '分析対象の単位');
  [
    ['overall', 'インタビュー全体', '会話全体の流れ・構造・統計を確認'],
    ['speakers', '話者ごと', '個人の発話量・語彙・属性を確認']
  ].forEach(([scope, titleText, description]) => {
    const active = analysisState.automaticScope === scope;
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisScope = scope;
    button.setAttribute('aria-pressed', String(active));
    button.append(
      analysisElement('strong', '', titleText),
      analysisElement('span', '', description)
    );
    switcher.append(button);
  });
  return switcher;
}

function analysisSpeakerRoleText(metric) {
  const label = role => Object.hasOwn(speakerRoleLabels, role) ? speakerRoleLabels[role] : String(role || '役割未設定');
  if (metric?.role_status === 'mixed') {
    const roles = Array.isArray(metric.observed_roles) ? metric.observed_roles.map(label).join('・') : '';
    return roles ? `役割混在（${roles}）` : '役割混在';
  }
  return label(metric?.role);
}

function analysisSpeakerAttributeValue(metric, key) {
  const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
  if (key === 'role') return analysisSpeakerRoleText(metric);
  if (key === 'tags') return (Array.isArray(profile.tags) ? profile.tags : []).join('・');
  if (key.startsWith('custom:')) {
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    return String(attributes[key.slice(7)] || '').trim();
  }
  return String(profile[key] || '').trim();
}

function analysisSpeakerAttributeDimensions(speakers) {
  const fixed = [
    ['role', '役割'],
    ['organization', '組織'],
    ['department', '部署'],
    ['job_title', '役職'],
    ['conditions', '会話固有条件'],
    ['tags', 'タグ']
  ];
  const customKeys = new Set();
  speakers.forEach(metric => {
    const profile = metric && typeof metric.profile === 'object' ? metric.profile : {};
    const attributes = profile.attributes && typeof profile.attributes === 'object' ? profile.attributes : {};
    Object.keys(attributes).forEach(key => customKeys.add(key));
  });
  const candidates = [
    ...fixed,
    ...[...customKeys].sort((a, b) => a.localeCompare(b, 'ja')).map(key => [`custom:${key}`, key])
  ];
  return candidates
    .map(([key, label]) => ({
      key,
      label,
      values: [...new Set(speakers.map(metric => analysisSpeakerAttributeValue(metric, key)).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'ja', {numeric: true, sensitivity: 'base'}))
    }))
    .filter(dimension => dimension.values.length);
}

function sortedAnalysisSpeakers(speakers, sortKey) {
  const values = [...speakers];
  const nameCompare = (a, b) => String(a.speaker_name || a.speaker).localeCompare(
    String(b.speaker_name || b.speaker), 'ja', {numeric: true, sensitivity: 'base'}
  );
  if (sortKey === 'speaker_name') return values.sort(nameCompare);
  if (sortKey === 'speaker_label') {
    return values.sort((a, b) => String(a.speaker).localeCompare(String(b.speaker), 'ja', {numeric: true}));
  }
  if (sortKey.startsWith('attribute:')) {
    const attributeKey = sortKey.slice(10);
    return values.sort((a, b) => {
      const valueA = analysisSpeakerAttributeValue(a, attributeKey);
      const valueB = analysisSpeakerAttributeValue(b, attributeKey);
      if (!valueA && valueB) return 1;
      if (valueA && !valueB) return -1;
      return valueA.localeCompare(valueB, 'ja', {numeric: true, sensitivity: 'base'}) || nameCompare(a, b);
    });
  }
  return values.sort((a, b) => Number(a.speaking_seconds == null) - Number(b.speaking_seconds == null)
    || Number(b.speaking_seconds || 0) - Number(a.speaking_seconds || 0) || nameCompare(a, b));
}

function buildAnalysisSpeakerTimelineChart(metric, bins) {
  const module = analysisElement('div', 'analysis-chart-module');
  const explanation = analysisElement('div', 'analysis-chart-explanation');
  explanation.append(
    analysisElement('strong', '', `${metric.speaker_name || metric.speaker}の発話タイミング`),
    analysisElement('span', '', '各時間帯にこの話者が発話した秒数を示します。')
  );
  if (metric.timed_turn_count === 0 && metric.missing_time_turn_count > 0) {
    module.append(explanation, analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、この話者の時間推移は表示できません。'));
    return module;
  }
  const stage = analysisElement('div', 'analysis-chart-stage');
  stage.append(buildAnalysisLineSvg([{
    id: metric.speaker,
    label: metric.speaker_name || metric.speaker,
    color: safeAnalysisColor(metric.color),
    values: bins.map(bin => Number(((bin.speakers || []).find(item => String(item.speaker) === String(metric.speaker)) || {}).seconds) || 0)
  }], bins));
  const legend = analysisElement('div', 'analysis-chart-legend');
  const entry = analysisElement('span');
  const marker = analysisElement('i');
  marker.style.backgroundColor = safeAnalysisColor(metric.color);
  entry.append(marker, document.createTextNode(metric.speaker_name || metric.speaker));
  legend.append(entry);
  module.append(explanation, stage, legend, analysisElement('p', 'analysis-chart-note', `${analysisObservedTimeText(metric)}。時刻あり発話だけを集計しています。時刻不明の発話は時間帯へ配置できません。`));
  return module;
}

function analysisMedian(values) {
  const sorted = values.map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function analysisDurationSummary(segments) {
  const durations = segments
    .filter(item => item.valid_time === true && item.duration != null && item.duration !== '')
    .map(item => Number(item.duration))
    .filter(value => Number.isFinite(value) && value >= 0);
  return {
    median: analysisMedian(durations),
    longest: durations.length ? Math.max(...durations) : null
  };
}

function renderSpeakerAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  if (!speakers.length) {
    fragment.append(analysisElement('p', 'analysis-no-data analysis-speaker-empty', '話者ごとの分析に利用できる発話データがありません。'));
    return fragment;
  }

  const dimensions = analysisSpeakerAttributeDimensions(speakers);
  const allowedSorts = new Set(['speaking_desc', 'speaker_name', 'speaker_label', ...dimensions.map(item => `attribute:${item.key}`)]);
  if (!allowedSorts.has(analysisState.speakerSort)) analysisState.speakerSort = 'speaking_desc';
  const activeDimension = analysisState.speakerSort.startsWith('attribute:')
    ? dimensions.find(item => item.key === analysisState.speakerSort.slice(10)) : null;
  if (analysisState.speakerAttributeFilter && (!activeDimension || !activeDimension.values.includes(analysisState.speakerAttributeFilter))) {
    analysisState.speakerAttributeFilter = '';
  }
  const sortedSpeakers = sortedAnalysisSpeakers(speakers, analysisState.speakerSort);
  const visibleSpeakers = analysisState.speakerAttributeFilter && activeDimension
    ? sortedSpeakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === analysisState.speakerAttributeFilter)
    : sortedSpeakers;
  const selected = visibleSpeakers.find(item => String(item.speaker) === String(analysisState.selectedSpeaker))
    || visibleSpeakers[0];
  if (selected) analysisState.selectedSpeaker = String(selected.speaker);

  const toolbar = analysisElement('section', 'analysis-speaker-toolbar');
  const toolbarIntro = analysisElement('div', 'analysis-speaker-toolbar-intro');
  toolbarIntro.append(
    analysisElement('span', '', 'SPEAKER ANALYSIS'),
    analysisElement('h2', '', '話者を並べ替えて個別に確認'),
    analysisElement('p', '', dimensions.length
      ? `登録済み属性 ${dimensions.length}項目を利用できます。属性順では同じ値の話者をまとめて表示します。`
      : '話者名・ラベル・発話量で並べ替えられます。話者管理で属性を付けると属性順も選択できます。')
  );
  const controls = analysisElement('div', 'analysis-speaker-sort-controls');
  const sortLabel = analysisElement('label');
  sortLabel.append(analysisElement('span', '', '並べ替え'));
  const sortSelect = document.createElement('select');
  [
    ['speaking_desc', '発話時間が長い順'],
    ['speaker_name', '話者名順'],
    ['speaker_label', '話者ラベル順']
  ].forEach(([value, label]) => sortSelect.add(new Option(label, value)));
  dimensions.forEach(item => sortSelect.add(new Option(`属性：${item.label}`, `attribute:${item.key}`)));
  sortSelect.value = analysisState.speakerSort;
  sortSelect.addEventListener('change', () => {
    analysisState.speakerSort = sortSelect.value;
    analysisState.speakerAttributeFilter = '';
    renderAnalysisWorkspace();
  });
  sortLabel.append(sortSelect);
  controls.append(sortLabel);
  if (activeDimension) {
    const filterLabel = analysisElement('label');
    filterLabel.append(analysisElement('span', '', `${activeDimension.label}で絞り込み`));
    const filterSelect = document.createElement('select');
    filterSelect.add(new Option('すべての属性値', ''));
    activeDimension.values.forEach(value => filterSelect.add(new Option(`${value}（${speakers.filter(item => analysisSpeakerAttributeValue(item, activeDimension.key) === value).length}人）`, value)));
    filterSelect.value = analysisState.speakerAttributeFilter;
    filterSelect.addEventListener('change', () => {
      analysisState.speakerAttributeFilter = filterSelect.value;
      analysisState.selectedSpeaker = '';
      renderAnalysisWorkspace();
    });
    filterLabel.append(filterSelect);
    controls.append(filterLabel);
  }
  const exportLink = analysisExportLink('話者別集計CSV', 'speakers', 'analysis-inline-export');
  if (exportLink) controls.append(exportLink);
  toolbar.append(toolbarIntro, controls);
  fragment.append(toolbar);

  const workspace = analysisElement('div', 'analysis-speaker-dashboard');
  const browser = analysisElement('aside', 'analysis-speaker-browser');
  const browserHeading = analysisElement('header');
  browserHeading.append(
    analysisElement('strong', '', `話者 ${visibleSpeakers.length} / ${speakers.length}人`),
    analysisElement('span', '', activeDimension ? `${activeDimension.label}順` : 'クリックして個別分析を表示')
  );
  browser.append(browserHeading);
  const list = analysisElement('div', 'analysis-speaker-list');
  let previousGroup = null;
  visibleSpeakers.forEach(metric => {
    const groupValue = activeDimension
      ? analysisSpeakerAttributeValue(metric, activeDimension.key) || '未設定' : '';
    if (activeDimension && groupValue !== previousGroup) {
      list.append(analysisElement('div', 'analysis-speaker-group-label', `${activeDimension.label}：${groupValue}`));
      previousGroup = groupValue;
    }
    const active = selected && String(metric.speaker) === String(selected.speaker);
    const button = analysisElement('button', active ? 'active' : '');
    button.type = 'button';
    button.dataset.analysisSpeakerId = metric.speaker;
    button.setAttribute('aria-pressed', String(active));
    button.style.setProperty('--speaker-color', safeAnalysisColor(metric.color));
    const identity = analysisElement('span', 'analysis-speaker-list-identity');
    identity.append(
      analysisElement('i'),
      analysisElement('strong', '', metric.speaker_name || metric.speaker)
    );
    const detail = activeDimension
      ? `${groupValue} / ${analysisObservedTimeText(metric)}`
      : `${analysisSpeakerRoleText(metric)} / ${analysisObservedTimeText(metric)}`;
    button.append(identity, analysisElement('small', '', detail));
    list.append(button);
  });
  if (!visibleSpeakers.length) list.append(analysisElement('p', 'analysis-no-data', 'この属性値に該当する話者はいません。'));
  browser.append(list);
  workspace.append(browser);

  const detail = analysisElement('section', 'analysis-speaker-detail');
  detail.setAttribute('aria-label', '選択した話者の分析');
  if (!selected) {
    detail.append(analysisElement('p', 'analysis-no-data', '左の一覧から話者を選択してください。'));
    workspace.append(detail);
    fragment.append(workspace);
    return fragment;
  }
  const detailHeader = analysisElement('section', 'analysis-speaker-detail-header');
  detailHeader.style.setProperty('--speaker-color', safeAnalysisColor(selected.color));
  const titleGroup = analysisElement('div');
  titleGroup.append(
    analysisElement('span', '', selected.speaker),
    analysisElement('h2', '', selected.speaker_name || selected.speaker),
    analysisElement('p', '', `${analysisSpeakerRoleText(selected)}の発話を、インタビュー全体との比率を保ったまま表示しています。`)
  );
  const profileAttributes = analysisElement('div', 'analysis-speaker-attributes');
  dimensions.forEach(dimension => {
    const value = analysisSpeakerAttributeValue(selected, dimension.key);
    if (!value) return;
    const chip = analysisElement('span');
    chip.append(analysisElement('small', '', dimension.label), document.createTextNode(value));
    profileAttributes.append(chip);
  });
  if (!profileAttributes.childNodes.length) profileAttributes.append(analysisElement('span', 'empty', '登録属性なし'));
  detailHeader.append(titleGroup, profileAttributes);
  detail.append(detailHeader);

  const metrics = analysisElement('div', 'analysis-overview analysis-speaker-overview');
  appendAnalysisMetric(metrics, '発話時間', analysisObservedTimeText(selected), analysisNumberText(selected.speaking_percent, 1, '%'));
  appendAnalysisMetric(metrics, '発話回数', `${selected.turn_count || 0}回`, `平均 ${analysisNumberText(selected.average_turn_seconds, 1, '秒')}`);
  appendAnalysisMetric(metrics, '文字数', `${selected.characters || 0}字`, `${analysisNumberText(selected.characters_per_minute, 1)}字/分`);
  appendAnalysisMetric(metrics, '質問候補', `${selected.question_candidates || 0}件`);
  appendAnalysisMetric(metrics, '最初の発話', selected.first_start == null ? '—' : formatTime(selected.first_start));
  appendAnalysisMetric(metrics, '最後の発話', selected.last_end == null ? '—' : formatTime(selected.last_end));
  detail.append(metrics);

  const detailGrid = analysisElement('div', 'analysis-grid analysis-speaker-detail-grid');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const timelinePanel = analysisCardPanel('この話者の時間推移', 'automatic', '', true);
  if (bins.length) timelinePanel.body.append(buildAnalysisSpeakerTimelineChart(selected, bins));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時間推移を表示できません。'));
  detailGrid.append(timelinePanel.panel);

  const research = data.research || {};
  const linguistics = research.linguistics || {};
  const speakerTermRows = Array.isArray(linguistics.speaker_term_frequency) ? linguistics.speaker_term_frequency : [];
  const speakerTerms = speakerTermRows.find(item => String(item.speaker) === String(selected.speaker)) || {};
  const termsPanel = analysisCardPanel('この話者の内容語', 'automatic');
  const terms = Array.isArray(speakerTerms.terms) ? speakerTerms.terms : [];
  const maxTerm = Math.max(1, ...terms.map(item => Number(item.term_frequency) || 0));
  terms.slice(0, compact ? 10 : 15).forEach(item => appendSearchableTermBar(
    termsPanel.body,
    item.term,
    100 * (Number(item.term_frequency) || 0) / maxTerm,
    `TF ${item.term_frequency || 0} / DF ${item.document_frequency || 0} / ${item.upos || '—'}`,
    selected.color,
    selected.speaker
  ));
  if (!terms.length) termsPanel.body.append(analysisElement('p', 'analysis-no-data', 'この話者の内容語を抽出できませんでした。'));
  termsPanel.body.append(analysisElement('p', 'analysis-caption', `内容語 ${speakerTerms.content_token_count || 0}件 / 異なり語 ${speakerTerms.unique_term_count || 0}件。GiNZA/Sudachiの解析結果を話者内で再集計しています。`));
  detailGrid.append(termsPanel.panel);

  const distributionPanel = analysisCardPanel('話者内の発話分布', 'automatic');
  const speakerSegments = (Array.isArray(data.segments) ? data.segments : [])
    .filter(item => String(item.speaker) === String(selected.speaker) && !item.excluded);
  const durationSummary = analysisDurationSummary(speakerSegments);
  const distributionMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(distributionMetrics, '中央値', analysisNumberText(durationSummary.median, 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '最長発話', analysisNumberText(durationSummary.longest, 2, '秒'));
  appendAnalysisMetric(distributionMetrics, '質問候補率', analysisNumberText(100 * speakerSegments.filter(item => item.question_candidate).length / Math.max(1, speakerSegments.length), 1, '%'));
  appendAnalysisMetric(distributionMetrics, '内容語多様性', speakerTerms.content_token_count
    ? analysisNumberText(100 * Number(speakerTerms.unique_term_count || 0) / Number(speakerTerms.content_token_count), 1, '%') : '—');
  distributionPanel.body.append(distributionMetrics, analysisElement('p', 'analysis-caption', '話者内の記述値です。話者間の優劣や発言の重要性を示すものではありません。'));
  detailGrid.append(distributionPanel.panel);

  const emotionPanel = analysisCardPanel('感情推定・手動コード', 'automatic');
  const emotionCounts = selected.emotion_counts && typeof selected.emotion_counts === 'object' ? selected.emotion_counts : {};
  const codeCounts = selected.code_counts && typeof selected.code_counts === 'object' ? selected.code_counts : {};
  const codeLabels = new Map(((data.manual || {}).codebook || []).map(item => [String(item.id), item.label || item.id]));
  const summaryRows = [
    ...Object.entries(emotionCounts).map(([label, count]) => [`感情推定 / ${label}`, count]),
    ...Object.entries(codeCounts).map(([id, count]) => [`手動コード / ${codeLabels.get(String(id)) || id}`, count])
  ].sort((a, b) => Number(b[1]) - Number(a[1]));
  summaryRows.forEach(([label, count]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('strong', '', label), analysisElement('span', '', `${count}件`));
    emotionPanel.body.append(row);
  });
  if (!summaryRows.length) emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '感情推定または手動コードの集計はありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', '感情はモデル推定、コードは研究者による付与です。両者を同じ尺度として比較しないでください。'));
  detailGrid.append(emotionPanel.panel);

  const transitionPanel = analysisCardPanel('この話者との話者交替', 'automatic', '', true);
  const transitions = (Array.isArray(automatic.transitions) ? automatic.transitions : [])
    .filter(item => String(item.from_speaker) === String(selected.speaker) || String(item.to_speaker) === String(selected.speaker))
    .sort((a, b) => Number(b.count || 0) - Number(a.count || 0));
  if (transitions.length) {
    const wrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['方向', '相手話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 10 : 20).forEach(item => {
      const outgoing = String(item.from_speaker) === String(selected.speaker);
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', outgoing ? 'この話者 → 相手' : '相手 → この話者'),
        analysisElement('td', '', outgoing ? item.to_name || item.to_speaker : item.from_name || item.from_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    transitionPanel.body.append(wrap);
  } else transitionPanel.body.append(analysisElement('p', 'analysis-no-data', '他の話者との交替データがありません。'));
  transitionPanel.body.append(analysisElement('p', 'analysis-caption', '話者交替の回数は影響・同意・対立を意味しません。前後の発話を確認してください。'));
  detailGrid.append(transitionPanel.panel);

  const utterancePanel = analysisCardPanel('この話者の発話一覧', 'automatic', '', true);
  const utteranceList = analysisElement('div', 'analysis-speaker-utterances');
  speakerSegments.slice(0, compact ? 12 : 30).forEach(item => {
    const article = analysisElement('article', 'analysis-speaker-utterance');
    article.append(
      analysisElement('time', '', `${formatTime(item.start || 0)}–${formatTime(item.end || 0)}`),
      analysisElement('p', '', item.text || '（本文なし）')
    );
    utteranceList.append(article);
  });
  if (!speakerSegments.length) utteranceList.append(analysisElement('p', 'analysis-no-data', '表示できる発話がありません。'));
  utterancePanel.body.append(utteranceList);
  if (speakerSegments.length > (compact ? 12 : 30)) {
    utterancePanel.body.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${compact ? 12 : 30}件を表示しています。全件は発話データCSVまたはExcelで確認できます。`));
  }
  detailGrid.append(utterancePanel.panel);
  detail.append(detailGrid);
  workspace.append(detail);
  fragment.append(workspace);
  return fragment;
}

// Method-specific analysis rendering is in analysis-method-view.js.

function renderAutomaticAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const data = analysisState.data || {};
  const automatic = data.automatic || {};
  const overview = automatic.overview || {};
  const speakerScope = analysisState.automaticScope === 'speakers';
  const intro = analysisElement('div', 'analysis-result-intro');
  intro.dataset.analysisAnchor = 'overview';
  intro.append(
    analysisElement('span', 'analysis-kind automatic', '自動集計'),
    analysisElement('h2', '', speakerScope
      ? '話者ごとの会話データ分析'
      : '会話全体の分析結果'),
    analysisElement('p', '', speakerScope
      ? '話者を選び、発話量・時間推移・内容語・話者交替・登録属性を個別に確認します。属性は比較や並べ替えのための記述情報です。'
      : '概要から傾向をつかみ、気になる項目を選んで根拠の発話を確認できます。')
  );
  fragment.append(intro, buildAnalysisScopeSwitch());

  if (speakerScope) {
    fragment.append(renderSpeakerAnalysis(compact));
    return fragment;
  }

  const metrics = analysisElement('div', 'analysis-overview');
  appendAnalysisMetric(metrics, '時刻ありの最終終了位置', analysisEndpointText(overview.session_duration, overview.session_timed_turn_count, overview.session_missing_time_turn_count), '除外を含む全発話の時刻。録音ファイルの全長ではありません');
  appendAnalysisMetric(metrics, '対象発話', `${overview.included_segment_count || 0}件`, `全${overview.segment_count || 0}件`);
  appendAnalysisMetric(metrics, '話者', `${overview.speaker_count || 0}人`);
  appendAnalysisMetric(metrics, '実際の参加者', overview.participant_count === null || overview.participant_count === undefined ? '未登録' : `${overview.participant_count}人`, '研究者が準備画面で登録した人数');
  appendAnalysisMetric(metrics, '観測された参加発言者', overview.observed_participant_count == null ? '不明' : `${overview.observed_participant_count}人`, overview.mixed_role_speaker_count > 0 ? '同じ話者の役割が混在するため人数を確定できません' : 'UNKNOWNを除外・実参加人数とは別');
  appendAnalysisMetric(metrics, '発話時間（時刻あり）', analysisObservedTimeText(overview, 'total_speaking_seconds'));
  fragment.append(metrics);

  const observations = Array.isArray(automatic.observations) ? automatic.observations : [];
  if (observations.length) {
    const box = analysisElement('section', 'analysis-observations');
    box.append(analysisElement('h3', '', '確認候補'));
    observations.forEach(item => {
      const row = analysisElement('article', item.level === 'attention' ? 'attention' : 'info');
      row.append(analysisElement('strong', '', item.label || '確認候補'), analysisElement('p', '', item.message || ''));
      box.append(row);
    });
    fragment.append(box);
  }

  const summary = analysisElement('section', 'analysis-page');
  summary.dataset.analysisPage = 'overview';
  summary.setAttribute('aria-label', '概要');
  const observationsBox = fragment.querySelector('.analysis-observations');
  if (observationsBox) summary.append(observationsBox);
  summary.append(buildInsightSummary());
  const contentPage = analysisElement('section', 'analysis-page');
  contentPage.dataset.analysisPage = 'content';
  contentPage.setAttribute('aria-label', '内容・文脈検索');
  contentPage.append(buildContentExplorer(), buildSegmentClassificationPanel(compact), buildTransformerAnalysisPanel());
  fragment.append(buildAnalysisNavigation(), summary, contentPage);

  const grid = analysisElement('div', 'analysis-grid');
  grid.append(analysisSectionHeading(
    'conversation', '01 / CONVERSATION FLOW', '会話の流れを見る',
    'まず時間推移と話者別の参加量を見て、次に話者交替・無音・重なりの候補を確認します。'
  ));
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  const timelinePanel = analysisCardPanel('発話量の変化（時間別）', 'automatic', 'timeline', true, 'participation');
  const bins = Array.isArray(automatic.time_bins) ? automatic.time_bins : [];
  const allTimeMissing = overview.timed_turn_count === 0 && overview.missing_time_turn_count > 0;
  if (bins.length && !allTimeMissing) timelinePanel.body.append(buildAnalysisTimelineChart(bins, speakers));
  else timelinePanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、時間推移を表示できません。'));
  grid.append(timelinePanel.panel);

  const excitementPanel = analysisCardPanel('盛り上がりと議題・話題（時間別）', 'automatic', '', true, 'conversation_dynamics');
  if (allTimeMissing) excitementPanel.body.append(analysisElement('p', 'analysis-no-data', '時刻付きの発話がないため、活発度は算出できません。'));
  else excitementPanel.body.append(buildAnalysisExcitementChart(bins, data.session_outline));
  grid.append(excitementPanel.panel);

  const speakerPanel = analysisCardPanel('話者ごとの発話量', 'automatic', 'speakers', true, 'participation');
  if (!speakers.length) {
    speakerPanel.body.append(analysisElement('p', 'analysis-no-data', '発話データがありません。'));
  } else {
    speakers.forEach(item => {
      appendAnalysisBar(
        speakerPanel.body,
        item.speaker_name || item.speaker || '話者',
        item.speaking_percent,
        `${analysisNumberText(item.speaking_percent, 1, '%')} / ${analysisObservedTimeText(item)} / ${item.turn_count || 0}回`,
        item.color
      );
    });
  }
  grid.append(speakerPanel.panel);

  const balance = automatic.balance || {};
  const balancePanel = analysisCardPanel(balance.denominator === 'observed_speakers' ? '全観測話者の発言バランス' : '参加者の発言バランス', 'automatic', '', false, 'participation');
  const balanceMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(balanceMetrics, '均等度', balance.normalized_evenness == null ? '未計算' : analysisNumberText(Number(balance.normalized_evenness) * 100, 1, '%'), '観測発言者内で100%に近いほど均等');
  appendAnalysisMetric(balanceMetrics, '最大比率', analysisNumberText(balance.max_participant_percent, 1, '%'), balance.max_participant_name || '—');
  appendAnalysisMetric(balanceMetrics, 'Gini係数', analysisNumberText(balance.gini, 3), '0に近いほど均等');
  balancePanel.body.append(balanceMetrics, analysisElement('p', 'analysis-caption', `${balance.denominator_label || '観測された発言者内'} / 分母 ${balance.balance_speaker_count ?? '—'}人。${balance.denominator_note || ''} 時刻欠測 ${balance.missing_time_turn_count ?? '—'}発話。発言量の偏りを示す記述値で、発言の重要性や影響力ではありません。`));
  if (balance.unavailable_reason === 'mixed_roles') balancePanel.body.append(analysisElement('p', 'content-inline-notice', '同じ話者の役割が混在するため、参加者内の割合・均等度は算出できません。全体時間は保持しています。'));
  grid.append(balancePanel.panel);

  const moderatorPanel = analysisCardPanel('司会者と参加者の発言関係', 'automatic', '', false, 'participation');
  const moderator = automatic.moderator || {};
  const moderatorMetrics = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(moderatorMetrics, '司会発話比率', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : moderator.assigned ? analysisNumberText(moderator.speaking_percent, 1, '%') : '役割未設定');
  appendAnalysisMetric(moderatorMetrics, '質問候補', moderator.role_aggregation_status === 'mixed' ? '役割混在で算出不可' : analysisNumberText(moderator.question_candidates, 0, '件'));
  appendAnalysisMetric(moderatorMetrics, '参加者応答', `${moderator.participant_responses || 0}件`);
  appendAnalysisMetric(moderatorMetrics, '参加者間遷移', `${moderator.participant_to_participant_transitions || 0}件`);
  moderatorPanel.body.append(moderatorMetrics, analysisElement('p', 'analysis-caption', '質問・応答は表記と話者遷移からの候補です。進行品質の評価ではありません。'));
  grid.append(moderatorPanel.panel);

  const transitionsPanel = analysisCardPanel('発言者の交替パターン', 'automatic', 'transitions', true, 'conversation_dynamics');
  const transitions = Array.isArray(automatic.transitions) ? automatic.transitions : [];
  if (transitions.length) {
    const tableWrap = analysisElement('div', 'analysis-table-wrap');
    const table = analysisElement('table', 'analysis-table');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    ['前の話者', '次の話者', '回数', '平均間隔', '重なり候補'].forEach(value => headRow.append(analysisElement('th', '', value)));
    head.append(headRow);
    const body = analysisElement('tbody');
    transitions.slice(0, compact ? 8 : 20).forEach(item => {
      const row = analysisElement('tr');
      row.append(
        analysisElement('td', '', item.from_name || item.from_speaker),
        analysisElement('td', '', item.to_name || item.to_speaker),
        analysisElement('td', '', item.count || 0),
        analysisElement('td', '', analysisNumberText(item.average_gap_seconds, 2, '秒')),
        analysisElement('td', '', item.overlap_candidates || 0)
      );
      body.append(row);
    });
    table.append(head, body);
    tableWrap.append(table);
    transitionsPanel.body.append(tableWrap, analysisElement('p', 'analysis-caption', '遷移回数は影響関係や同意を意味しません。'));
  } else transitionsPanel.body.append(analysisElement('p', 'analysis-no-data', '話者交替のデータがありません。'));
  grid.append(transitionsPanel.panel);

  const gapsPanel = analysisCardPanel('沈黙・同時発話の候補', 'automatic', 'gaps', false, 'conversation_dynamics');
  const longGaps = Array.isArray(automatic.long_gaps) ? automatic.long_gaps : [];
  const overlaps = Array.isArray(automatic.overlap_candidates) ? automatic.overlap_candidates : [];
  const gapSummary = analysisElement('div', 'analysis-mini-metrics');
  appendAnalysisMetric(gapSummary, '長い無音候補', `${longGaps.length}件`);
  appendAnalysisMetric(gapSummary, '重なり候補', `${overlaps.length}件`);
  gapsPanel.body.append(gapSummary);
  const overlapExport = analysisExportLink('重なりCSV', 'overlaps', 'analysis-inline-export');
  if (overlapExport) gapsPanel.body.append(overlapExport);
  gapsPanel.body.append(analysisElement('p', 'analysis-caption', '沈黙・遮り・熱意などの意味は音声と文脈を確認して判断してください。'));
  grid.append(gapsPanel.panel);

  const emotionPanel = analysisCardPanel('声から推定した感情の分布', 'automatic', 'emotions', false, 'audio_emotion');
  const emotions = Array.isArray(automatic.emotions) ? automatic.emotions : [];
  if (emotions.length) {
    emotions.slice(0, compact ? 10 : 20).forEach(item => {
      const row = analysisElement('div', 'analysis-list-row');
      const emotionLabel = [
        item.speaker_name || item.speaker,
        item.model_name || item.model || '感情モデル',
        item.label || item.emotion
      ].filter(Boolean).join(' / ');
      row.append(
        analysisElement('strong', '', emotionLabel),
        analysisElement('span', '', `${item.count || 0}件 / ${analysisObservedTimeText(item, 'seconds')}`)
      );
      emotionPanel.body.append(row);
    });
  } else emotionPanel.body.append(analysisElement('p', 'analysis-no-data', '音声感情分析が未実行、または利用できる推定値がありません。'));
  emotionPanel.body.append(analysisElement('p', 'analysis-caption', 'モデル推定は本人の感情を確定するものではありません。'));
  grid.append(emotionPanel.panel);

  const groups = Array.isArray(automatic.groups) ? automatic.groups : [];
  if (groups.length) {
    const groupsPanel = analysisCardPanel('話者グループの比較', 'configured', 'groups', false, 'participation');
    groups.forEach(item => appendAnalysisBar(
      groupsPanel.body, item.group || '未設定', item.speaking_percent,
      `${item.speaker_count || 0}人 / ${item.turn_count || 0}回 / ${analysisObservedTimeText(item)}`,
      '#9B51E0'
    ));
    grid.append(groupsPanel.panel);
  }

  grid.append(analysisSectionHeading(
    'language', '02 / LANGUAGE STRUCTURE', '語と構文を探索する',
    '特徴語から全体像をつかみ、形態素・共起関係・文ごとの係り受けへ段階的に掘り下げます。'
  ));
  const keywordsPanel = analysisCardPanel('会話でよく使われた特徴語', 'automatic', 'keywords', false, 'lexical_frequency');
  const keywords = Array.isArray(automatic.keywords) ? automatic.keywords : [];
  const maxKeyword = Math.max(1, ...keywords.map(item => Number(item.count) || 0));
  if (keywords.length) {
    keywords.slice(0, compact ? 10 : 15).forEach(item => appendAnalysisBar(
      keywordsPanel.body, item.term, 100 * (Number(item.count) || 0) / maxKeyword, `${item.count || 0}回`, '#6C8B3C'
    ));
  } else keywordsPanel.body.append(analysisElement('p', 'analysis-no-data', '特徴語候補を抽出できませんでした。'));
  keywordsPanel.body.append(analysisElement('p', 'analysis-caption', '出現頻度による簡易候補で、研究テーマを自動決定するものではありません。'));
  grid.append(keywordsPanel.panel);

  appendResearchAnalysis(grid, compact);

  const qualityPanel = analysisCardPanel('分析に使ったデータの確認', 'automatic');
  const quality = automatic.data_quality || {};
  const qualityList = analysisElement('div', 'analysis-quality-list');
  [
    ['話者未判定の発話', `${quality.unknown_speaker_segments || 0}件`],
    ['本文が空の発話', `${quality.empty_text_segments || 0}件`],
    ['時間が0秒の発話', `${quality.zero_duration_segments || 0}件`],
    ['時刻が不正な発話', `${quality.invalid_time_segments || 0}件`],
    ['感情データ範囲', analysisNumberText(quality.emotion_coverage_percent, 1, '%')],
    ['分析から除外', `${quality.excluded_segments || 0}件`]
  ].forEach(([label, value]) => {
    const row = analysisElement('div', 'analysis-list-row');
    row.append(analysisElement('span', '', label), analysisElement('strong', '', value));
    qualityList.append(row);
  });
  qualityPanel.body.append(qualityList);
  grid.append(qualityPanel.panel);
  grid.append(analysisExportDirectory('自動分析データの出力', 'automatic', [
    ['summary', '概要 CSV'],
    ['observations', '確認候補 CSV'],
    ['speakers', '話者別発話量 CSV'],
    ['transitions', '話者遷移 CSV'],
    ['gaps', '無音候補 CSV'],
    ['overlaps', '重なり候補 CSV'],
    ['keywords', '特徴語候補 CSV'],
    ['emotions', '感情推定 CSV'],
    ['timeline', '時間推移 CSV'],
    ['groups', '属性比較 CSV']
  ]));
  // Keep existing panels and controls mounted when switching sections. This
  // preserves search input, running-job status, and the method view's panels.
  let page;
  [...grid.children].forEach(node => {
    if (node.dataset.analysisAnchor) {
      page = analysisElement('section', 'analysis-page analysis-grid');
      page.dataset.analysisPage = node.dataset.analysisAnchor;
      page.setAttribute('aria-label', node.querySelector('h2')?.textContent || '分析結果');
      fragment.append(page);
    }
    if (page) page.append(node);
  });
  fragment.querySelector('[data-analysis-page="exports"]')?.append(buildAnalysisStorage());
  applyAnalysisPage(fragment, analysisState.automaticPage);

  const cautions = Array.isArray(data.cautions) ? data.cautions : [];
  if (cautions.length) {
    const details = analysisElement('details', 'analysis-cautions');
    details.append(analysisElement('summary', '', '分析値を読むときの注意'));
    const list = analysisElement('ul');
    cautions.forEach(value => list.append(analysisElement('li', '', value)));
    details.append(list);
    fragment.append(details);
  }
  return fragment;
}

function analysisField(labelText, control, noteText = '') {
  const label = analysisElement('label', 'field analysis-field');
  label.append(analysisElement('span', '', labelText), control);
  if (noteText) label.append(analysisElement('small', '', noteText));
  return label;
}

function analysisGroupByOptions() {
  const options = {
    none: '比較しない',
    role: '会話役割',
    organization: '組織',
    department: '部署',
    job_title: '役職'
  };
  const automatic = analysisState.data && analysisState.data.automatic || {};
  const speakers = Array.isArray(automatic.speaker_metrics) ? automatic.speaker_metrics : [];
  analysisSpeakerAttributeDimensions(speakers)
    .filter(dimension => dimension.key.startsWith('custom:'))
    .forEach(dimension => {
      const key = dimension.key.slice('custom:'.length);
      options[`attribute:${key}`] = `事前アンケート：${dimension.label}`;
    });
  const current = String(analysisState.config.group_by || '');
  if (current.startsWith('attribute:') && !options[current]) {
    options[current] = `事前アンケート：${current.slice('attribute:'.length)}`;
  }
  return options;
}

function analysisConfigControl(field, type = 'text', options = null) {
  const value = analysisState.config[field];
  let control;
  if (type === 'textarea') {
    control = document.createElement('textarea');
    control.rows = field === 'research_question' || field === 'analyst_memo' ? 4 : 2;
    control.value = value || '';
  } else if (type === 'select') {
    control = document.createElement('select');
    Object.entries(options || {}).forEach(([optionValue, label]) => control.add(new Option(label, optionValue)));
    control.value = value === undefined || value === null ? '' : String(value);
  } else {
    control = document.createElement('input');
    control.type = type;
    if (type === 'checkbox') control.checked = Boolean(value);
    else control.value = value === undefined || value === null ? '' : String(value);
  }
  control.dataset.analysisConfig = field;
  return control;
}

function analysisMatchModeLabel(mode) {
  return ({normalized: '正規化語の完全一致', surface: '表層語の完全一致', literal: '本文の部分一致（大文字小文字を区別）'})[mode] || '一致条件未確認';
}

function analysisTermCrosstabSelector(compact) {
  const container = analysisElement('div', 'analysis-term-selector');
  const selected = Array.isArray(analysisState.config.crosstab_terms)
    ? analysisState.config.crosstab_terms
    : [];
  const input = analysisConfigControl('crosstab_terms', 'text');
  input.placeholder = '例：改善, 価格, 使いやすい';
  container.append(
    analysisField(
      'クロス集計＋カイ二乗検定をする単語',
      input,
      'カンマ・読点・改行区切り。最大30語。発話ごとの「あり／なし」と統計の比較軸を集計します。'
    )
  );

  container.append(analysisField('語の一致条件（文脈検索と共通）', analysisConfigControl('crosstab_match_mode', 'select', {normalized: analysisMatchModeLabel('normalized'), surface: analysisMatchModeLabel('surface'), literal: analysisMatchModeLabel('literal')})));
  const candidates = (((analysisState.data || {}).research || {}).linguistics || {}).term_frequency || [];
  const candidateWrap = analysisElement('div', 'analysis-term-candidates');
  candidateWrap.append(analysisElement('span', '', '頻出語から選択'));
  candidates.slice(0, compact ? 16 : 30).forEach(item => {
    const term = String(item.term || '').trim();
    if (!term) return;
    const button = analysisElement('button', selected.includes(term) ? 'active' : '', term);
    button.type = 'button';
    button.dataset.analysisCrosstabTerm = term;
    button.setAttribute('aria-pressed', selected.includes(term) ? 'true' : 'false');
    candidateWrap.append(button);
  });
  if (!candidates.length) candidateWrap.append(analysisElement('small', '', '候補語は分析実行後に表示されます。'));

  const action = analysisElement('button', 'primary-button small analysis-run-term-test', '選択した単語で検定を実行');
  action.type = 'button';
  action.dataset.analysisRunTermCrosstab = 'true';
  container.append(candidateWrap, action);
  return container;
}

function analysisCodebookEditor(compact) {
  const container = analysisElement('div', 'analysis-codebook');
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  if (!codebook.length) {
    container.append(analysisElement('p', 'analysis-no-data', 'コードはまだありません。研究質問に沿ってコード名と定義を追加してください。'));
  }
  codebook.forEach((code, index) => {
    const card = analysisElement(compact ? 'details' : 'article', 'analysis-code-card');
    if (compact) {
      const summary = analysisElement('summary');
      const swatch = analysisElement('i');
      swatch.style.backgroundColor = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
      summary.append(swatch, analysisElement('strong', '', code.label || `コード ${index + 1}`));
      card.append(summary);
    }
    const body = analysisElement('div', 'analysis-code-body');
    const top = analysisElement('div', 'analysis-code-top');
    const color = document.createElement('input');
    color.type = 'color';
    color.value = safeAnalysisColor(code.color, speakerThemeColors[index % speakerThemeColors.length]);
    color.dataset.analysisCodeId = code.id;
    color.dataset.analysisCodeField = 'color';
    color.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}の色`);
    const label = document.createElement('input');
    label.type = 'text';
    label.maxLength = 120;
    label.value = code.label || '';
    label.placeholder = 'コード名';
    label.dataset.analysisCodeId = code.id;
    label.dataset.analysisCodeField = 'label';
    const remove = analysisElement('button', 'analysis-remove-code', '削除');
    remove.type = 'button';
    remove.dataset.analysisRemoveCode = code.id;
    remove.setAttribute('aria-label', `${code.label || `コード ${index + 1}`}を削除`);
    top.append(color, label, remove);
    body.append(top);
    [
      ['category', 'カテゴリー', '例：利用上の課題'],
      ['theme', 'テーマ', '例：導入を阻む負担']
    ].forEach(([field, caption, placeholder]) => {
      const input = document.createElement('input');
      input.type = 'text';
      input.maxLength = 160;
      input.value = code[field] || '';
      input.placeholder = placeholder;
      input.dataset.analysisCodeId = code.id;
      input.dataset.analysisCodeField = field;
      body.append(analysisField(caption, input));
    });
    [
      ['description', '定義', 'このコードに含める意味・判断基準'],
      ['include_example', '含める例', '該当する発話の例'],
      ['exclude_example', '含めない例', '似ているが除外する発話の例']
    ].forEach(([field, caption, placeholder]) => {
      const textarea = document.createElement('textarea');
      textarea.rows = field === 'description' ? 3 : 2;
      textarea.maxLength = field === 'description' ? 4000 : 2000;
      textarea.value = code[field] || '';
      textarea.placeholder = placeholder;
      textarea.dataset.analysisCodeId = code.id;
      textarea.dataset.analysisCodeField = field;
      body.append(analysisField(caption, textarea));
    });
    card.append(body);
    container.append(card);
  });
  const add = analysisElement('button', 'secondary-button analysis-add-code', '＋ コードを追加');
  add.type = 'button';
  add.dataset.analysisAddCode = 'true';
  container.append(add);
  return container;
}

function analysisAnnotation(segmentId) {
  if (!analysisState.annotations[segmentId] || typeof analysisState.annotations[segmentId] !== 'object') {
    analysisState.annotations[segmentId] = {
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
  }
  return analysisState.annotations[segmentId];
}

function analysisSegmentMatches(segment) {
  const query = analysisState.segmentQuery.trim().toLocaleLowerCase();
  const annotation = analysisState.annotations[segment.id] || {};
  const annotated = Boolean(
    (annotation.codes || []).length
    || (annotation.interaction_tags || []).length
    || annotation.elicitation && annotation.elicitation !== 'unknown'
    || (annotation.interaction_links || []).length
    || annotation.memo
    || annotation.dialogue_act
    || annotation.importance_score !== undefined && annotation.importance_score !== null
    || annotation.review_score !== undefined && annotation.review_score !== null
    || annotation.sensitivity_score !== undefined && annotation.sensitivity_score !== null
    || annotation.classification_status && annotation.classification_status !== 'unreviewed'
    || annotation.classification_note
    || annotation.important
    || annotation.excluded
  );
  if (analysisState.annotatedOnly && !annotated) return false;
  if (!query) return true;
  return `${segment.speaker_name || ''} ${segment.speaker || ''} ${segment.text || ''}`
    .toLocaleLowerCase().includes(query);
}

function renderAnalysisSegmentItems(list, compact) {
  list.replaceChildren();
  const segments = Array.isArray(analysisState.data.segments) ? analysisState.data.segments : [];
  const visible = segments.filter(analysisSegmentMatches);
  const limit = compact ? 100 : 200;
  const count = analysisElement('p', 'analysis-segment-count', `表示 ${Math.min(visible.length, limit)} / 該当 ${visible.length} / 全 ${segments.length}発話`);
  list.append(count);
  if (!visible.length) {
    list.append(analysisElement('p', 'analysis-no-data', '条件に一致する発話がありません。'));
    return;
  }
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const interactionTags = ((analysisState.data.manual || {}).interaction_tags || []);
  const classificationResult = ((analysisState.data.segment_classification || {}).result || {});
  const proposalById = new Map((classificationResult.segments || []).map(row => [String(row.segment_id), row]));
  visible.slice(0, limit).forEach(segment => {
    const annotation = analysisState.annotations[segment.id] || {
      codes: [], interaction_tags: [], elicitation: 'unknown', interaction_links: [],
      dialogue_act: '', importance_score: null, review_score: null, sensitivity_score: null,
      classification_status: 'unreviewed', classification_note: '',
      memo: '', important: false, excluded: false
    };
    const card = analysisElement('article', 'analysis-segment-card');
    card.dataset.analysisSegmentCard = segment.id;
    const header = analysisElement('header');
    const meta = analysisElement('div');
    const speaker = analysisElement('strong', '', segment.speaker_name || segment.speaker || '話者未判定');
    speaker.style.borderColor = safeAnalysisColor(segment.color);
    meta.append(
      analysisElement('span', 'analysis-segment-time', `#${segment.utterance_order || '—'}`),
      analysisElement('span', 'analysis-segment-time', `${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`),
      speaker
    );
    const status = analysisElement('div', 'analysis-segment-status');
    if (annotation.important) status.append(analysisElement('span', 'important', '重要引用'));
    if (annotation.excluded) status.append(analysisElement('span', 'excluded', '分析除外'));
    header.append(meta, status);
    const quote = analysisElement('p', 'analysis-segment-text', segment.text || '（本文なし）');
    card.append(header, quote);

    const proposal = proposalById.get(String(segment.id));
    if (proposal) {
      const proposalGrid = analysisElement('div', 'segment-proposal-grid');
      const proposalCard = (label, value, source) => {
        const item = analysisElement('article');
        item.append(analysisElement('strong', '', label), analysisElement('span', '', value || '提案なし'));
        if (source && source.dialogue_act) {
          const apply = analysisElement('button', 'secondary-button small', '手動欄へ反映');
          apply.type = 'button';
          apply.dataset.applyClassificationProposal = source === proposal.llm ? 'llm' : 'template';
          apply.dataset.analysisSegmentId = segment.id;
          item.append(apply);
        }
        return item;
      };
      const scoreText = source => source && source.dialogue_act_label
        ? `${source.dialogue_act_label} / 重要${source.importance_score ?? '—'}・要確認${source.review_score ?? '—'}・機密${source.sensitivity_score ?? '—'}`
        : '';
      proposalGrid.append(
        proposalCard('テンプレート', scoreText(proposal.template), proposal.template),
        proposalCard('Jev', scoreText(proposal.llm), proposal.llm),
        proposalCard('Transformer話題', (proposal.transformer || {}).topic_label || '', null)
      );
      card.append(proposalGrid);
    }

    const classificationControls = analysisElement('div', 'segment-manual-classification');
    const dialogueAct = document.createElement('select');
    dialogueAct.add(new Option('未確定', ''));
    Object.entries(dialogueActLabels).forEach(([value, label]) => dialogueAct.add(new Option(label, value)));
    dialogueAct.value = annotation.dialogue_act || '';
    dialogueAct.dataset.analysisSegmentId = segment.id;
    dialogueAct.dataset.analysisAnnotationField = 'dialogue_act';
    classificationControls.append(analysisField('手動：発話種別', dialogueAct));
    [
      ['importance_score', '手動：重要度'],
      ['review_score', '手動：要確認度'],
      ['sensitivity_score', '手動：機密らしさ']
    ].forEach(([field, label]) => {
      const input = document.createElement('input');
      input.type = 'number'; input.min = '0'; input.max = '100'; input.step = '1';
      input.value = annotation[field] === undefined || annotation[field] === null ? '' : String(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      classificationControls.append(analysisField(label, input, '0〜100。空欄は未確定。'));
    });
    const classificationStatus = document.createElement('select');
    [['unreviewed', '未確認'], ['draft', '確認途中'], ['reviewed', '確認済み']]
      .forEach(([value, label]) => classificationStatus.add(new Option(label, value)));
    classificationStatus.value = annotation.classification_status || 'unreviewed';
    classificationStatus.dataset.analysisSegmentId = segment.id;
    classificationStatus.dataset.analysisAnnotationField = 'classification_status';
    classificationControls.append(analysisField('判定状態', classificationStatus));
    card.append(classificationControls);

    const classificationNote = document.createElement('textarea');
    classificationNote.rows = 2;
    classificationNote.maxLength = 5000;
    classificationNote.value = annotation.classification_note || '';
    classificationNote.placeholder = '自動提案を採用・修正・保留した根拠';
    classificationNote.dataset.analysisSegmentId = segment.id;
    classificationNote.dataset.analysisAnnotationField = 'classification_note';
    card.append(analysisField('分類確認メモ', classificationNote));

    const codeGroup = analysisElement('fieldset', 'analysis-chip-group');
    codeGroup.append(analysisElement('legend', '', 'テーマコード'));
    if (!codebook.length) codeGroup.append(analysisElement('p', 'analysis-inline-note', '先にコードブックへコードを追加してください。'));
    codebook.forEach(code => {
      const label = analysisElement('label', 'analysis-code-chip');
      label.style.setProperty('--code-color', safeAnalysisColor(code.color));
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.codes || []).includes(code.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'codes';
      input.dataset.analysisAnnotationValue = code.id;
      label.append(input, analysisElement('span', '', code.label));
      codeGroup.append(label);
    });
    card.append(codeGroup);

    const interactionGroup = analysisElement('details', 'analysis-interaction-group');
    interactionGroup.append(analysisElement('summary', '', '相互作用タグを確認・設定'));
    const chips = analysisElement('div', 'analysis-chip-group inline');
    interactionTags.forEach(tag => {
      const label = analysisElement('label', 'analysis-interaction-chip');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = (annotation.interaction_tags || []).includes(tag.id);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = 'interaction_tags';
      input.dataset.analysisAnnotationValue = tag.id;
      label.append(input, analysisElement('span', '', tag.label));
      chips.append(label);
    });
    interactionGroup.append(chips);
    card.append(interactionGroup);

    const elicitation = document.createElement('select');
    [
      ['unknown', '不明・未確認'], ['spontaneous', '自発的な発言'],
      ['moderator_prompted', '司会者の質問・働きかけを受けた発言'],
      ['participant_prompted', '他の参加者の働きかけを受けた発言'],
      ['other_prompted', 'その他の働きかけを受けた発言']
    ].forEach(([value, label]) => elicitation.add(new Option(label, value)));
    elicitation.value = annotation.elicitation || 'unknown';
    elicitation.dataset.analysisSegmentId = segment.id;
    elicitation.dataset.analysisAnnotationField = 'elicitation';
    card.append(analysisField('発話のきっかけ', elicitation, '自発か、誰の働きかけを受けたかを記録します。不明は推測で選びません。'));

    const evidenceGroup = analysisElement('details', 'analysis-interaction-group');
    evidenceGroup.append(analysisElement('summary', '', '根拠発話との相互作用リンク'));
    evidenceGroup.append(analysisElement('p', 'analysis-inline-note', '同意・反論・補足・変化は、対象となる発話を選び、根拠メモとともに結びます。単独タグだけからは意見形成を結論づけません。'));
    const linkControls = analysisElement('div', 'analysis-link-controls');
    const target = document.createElement('select');
    target.dataset.analysisInteractionTarget = segment.id;
    target.add(new Option('対象発話を選択', ''));
    const currentIndex = segments.findIndex(item => item.id === segment.id);
    segments.slice(Math.max(0, currentIndex - 12), currentIndex + 13)
      .filter(item => item.id !== segment.id)
      .forEach(item => target.add(new Option(
        `#${item.utterance_order || '—'} ${item.speaker_name || item.speaker}: ${String(item.text || '').slice(0, 42)}`,
        item.id
      )));
    const relation = document.createElement('select');
    relation.dataset.analysisInteractionRelation = segment.id;
    [
      ['response', '応答'], ['agreement', '同意・賛同'], ['disagreement', '不一致・反対'],
      ['differentiation', '立場の差異化'], ['change', '意見の変化'], ['word_use', '言葉の意味の違い'],
      ['repetition', '反復・強調'], ['engagement', '補足・発展']
    ].forEach(([value, label]) => relation.add(new Option(label, value)));
    const evidenceMemo = document.createElement('input');
    evidenceMemo.type = 'text';
    evidenceMemo.maxLength = 2000;
    evidenceMemo.placeholder = '根拠メモ（任意）';
    evidenceMemo.dataset.analysisInteractionMemo = segment.id;
    const addLink = analysisElement('button', 'secondary-button small', 'リンクを追加');
    addLink.type = 'button';
    addLink.dataset.analysisAddInteractionLink = segment.id;
    linkControls.append(target, relation, evidenceMemo, addLink);
    evidenceGroup.append(linkControls);
    const links = Array.isArray(annotation.interaction_links) ? annotation.interaction_links : [];
    if (links.length) {
      const list = analysisElement('ul', 'analysis-link-list');
      const relationLabels = {
        response: '応答', agreement: '同意・賛同', disagreement: '不一致・反対',
        differentiation: '立場の差異化', change: '意見の変化', word_use: '言葉の意味の違い',
        repetition: '反復・強調', engagement: '補足・発展'
      };
      links.forEach((link, index) => {
        const targetSegment = segments.find(item => item.id === link.target_segment_id) || {};
        const label = analysisElement('span', '', `${relationLabels[link.relation] || link.relation}：#${targetSegment.utterance_order || '—'} ${targetSegment.speaker_name || targetSegment.speaker || link.target_segment_id}`);
        const removeLink = analysisElement('button', 'secondary-button small', '削除');
        removeLink.type = 'button';
        removeLink.dataset.analysisRemoveInteractionLink = 'true';
        removeLink.dataset.analysisInteractionSource = segment.id;
        removeLink.dataset.analysisInteractionIndex = String(index);
        const row = analysisElement('li');
        row.append(label, removeLink);
        if (link.evidence_memo) row.append(analysisElement('small', '', link.evidence_memo));
        list.append(row);
      });
      evidenceGroup.append(list);
    }
    card.append(evidenceGroup);

    const flags = analysisElement('div', 'analysis-annotation-flags');
    [
      ['important', '重要引用として残す'],
      ['excluded', 'この発話を自動集計から除外']
    ].forEach(([field, labelText]) => {
      const label = analysisElement('label');
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = Boolean(annotation[field]);
      input.dataset.analysisSegmentId = segment.id;
      input.dataset.analysisAnnotationField = field;
      label.append(input, analysisElement('span', '', labelText));
      flags.append(label);
    });
    card.append(flags);
    const memo = document.createElement('textarea');
    memo.rows = compact ? 2 : 3;
    memo.maxLength = 5000;
    memo.value = annotation.memo || '';
    memo.placeholder = 'この発話の意味、文脈、例外、解釈メモ';
    memo.dataset.analysisSegmentId = segment.id;
    memo.dataset.analysisAnnotationField = 'memo';
    card.append(analysisField('発話メモ', memo));
    list.append(card);
  });
  if (visible.length > limit) {
    list.append(analysisElement('p', 'analysis-limit-note', `表示負荷を抑えるため先頭${limit}件を表示しています。検索で対象を絞り込んでください。`));
  }
}

function analysisCodingWorkspace(compact) {
  const container = analysisElement('div', 'analysis-coding-workspace');
  const toolbar = analysisElement('div', 'analysis-coding-toolbar');
  const search = document.createElement('input');
  search.type = 'search';
  search.value = analysisState.segmentQuery;
  search.placeholder = '発話本文・話者を検索';
  search.dataset.analysisSegmentQuery = 'true';
  const annotatedLabel = analysisElement('label', 'mini-check');
  const annotated = document.createElement('input');
  annotated.type = 'checkbox';
  annotated.checked = analysisState.annotatedOnly;
  annotated.dataset.analysisAnnotatedOnly = 'true';
  annotatedLabel.append(annotated, analysisElement('span', '', '設定済みだけ'));
  toolbar.append(analysisField('発話を検索', search), annotatedLabel);
  const list = analysisElement('div', 'analysis-segment-list');
  list.dataset.analysisSegmentList = compact ? 'mobile' : 'desktop';
  renderAnalysisSegmentItems(list, compact);
  container.append(toolbar, list);
  return container;
}

let preparationDraft = null;
let preparationDirty = false;
let preparationSaving = false;

function renderTranscriptPreparation() {
  const prepared = analysisState.data.manual?.preparation;
  const panel = analysisCardPanel('文字起こしを分析用データに整える', 'manual', 'prepared_turns', true);
  if (!prepared) return panel.panel;
  const key = `${analysisState.itemId}:${prepared.revision}:${prepared.source_hash}`;
  if (preparationDraft && preparationDirty && preparationDraft.source_hash === prepared.source_hash
      && preparationDraft.key.startsWith(`${analysisState.itemId}:`)) {
    preparationDraft.key = key;
    preparationDraft.revision = prepared.revision;
  }
  if (!preparationDraft || preparationDraft.key !== key) {
    preparationDraft = {key, revision: prepared.revision, source_hash: prepared.source_hash,
      order_verified: prepared.order_verified, participant_count: prepared.participant_count,
      metadata_sources: prepared.metadata_sources || '', review_analysis: false, records: {}};
    prepared.rows.forEach(row => {
      preparationDraft.records[row.segment_id] = Object.fromEntries(
        ['text_status', 'role', 'speaker_verified', 'boundary_verified', 'source_locator', 'source_segment_ids']
          .map(field => [field, deepCopy(row[field])])
      );
    });
  }
  const statusLabels = {draft: '確認途中', confirmed: '本文・区切り確認済みの版', needs_review: '入力変更後・要再確認'};
  panel.body.append(analysisElement('p', '',
    `入力版 ${prepared.input_version ?? '未固定'} / ${statusLabels[prepared.status]}。内容分析の準備: ${prepared.content_ready_count}/${prepared.rows.length}発言、相互作用の準備: ${prepared.interaction_ready_count}/${prepared.rows.length}発言。`));
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '取込原本は上書きしません。本文・話者・区切りは既存の文字起こし編集画面で修正してください。以下は修正した版の確認記録です。音声未照合や話者不明を確認済みとみなさず、資料がない人数は空欄にします。'));
  if (prepared.analysis_needs_review) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '既存のコード・相互作用は要再確認です。入力版または確認状態が変わりました。保存するだけでは解除されません。'));
  const exportLink = analysisElement('a', 'analysis-export-link', '原本・全入力版・確認履歴 JSON');
  exportLink.href = `/api/library/${encodeURIComponent(analysisState.itemId)}/preparation/export.json`;
  exportLink.download = '';
  panel.body.append(exportLink);
  const edit = analysisElement('button', 'secondary-button', '文字起こし編集を開く');
  edit.type = 'button';
  edit.addEventListener('click', () => {
    if (preparationDirty || analysisState.dirty) {
      setAlert(document.querySelector('#analysis-message'), '先に準備記録と分析設定を保存してください。', true);
      return;
    }
    openLibraryItem(analysisState.itemId);
  });
  panel.body.append(edit);
  const control = (label, field, options, sid = null) => {
    const object = sid ? preparationDraft.records[sid] : preparationDraft;
    const input = document.createElement(options && typeof options === 'object' ? 'select' : options === 'textarea' ? 'textarea' : 'input');
    if (input.tagName === 'SELECT') Object.entries(options).forEach(([value, text]) => input.append(new Option(text, value)));
    else if (input.tagName === 'INPUT') input.type = options || 'text';
    const value = object[field];
    if (input.type === 'checkbox') input.checked = Boolean(value);
    else input.value = Array.isArray(value) ? value.join(', ') : value ?? '';
    input.dataset.preparationKey = `${sid || 'session'}:${field}`;
    input.addEventListener('input', () => {
      object[field] = input.type === 'checkbox' ? input.checked
        : field === 'participant_count' ? (input.value === '' ? null : Number(input.value))
        : field === 'source_segment_ids' ? input.value.split(',').map(v => v.trim()).filter(Boolean) : input.value;
      preparationDirty = true;
      analysisMutationGeneration += 1;
      document.querySelectorAll('[data-preparation-key]').forEach(peer => {
        if (peer === input || peer.dataset.preparationKey !== input.dataset.preparationKey) return;
        if (input.type === 'checkbox') peer.checked = input.checked;
        else peer.value = input.value;
      });
    });
    return analysisField(label, input);
  };
  panel.body.append(
    control('資料・確認根拠（研究目的・質問票・参加者名簿等の資料名と位置。実名は不要）', 'metadata_sources', 'textarea'),
    control('実際の参加人数（不明は空欄。発言者数とは別）', 'participant_count', 'number'),
    control('保存されている発言の順序を原資料と確認した', 'order_verified', 'checkbox')
  );
  const turns = analysisElement('details');
  turns.append(analysisElement('summary', '', `発言ごとの確認（${prepared.rows.length}件）`));
  prepared.rows.forEach(row => {
    const detail = analysisElement('details', 'analysis-segment-card');
    detail.append(analysisElement('summary', '', `#${row.order} ${row.speaker_id || '話者不明'} / ${row.segment_id}`));
    const text = analysisElement('p', 'analysis-segment-text', row.text);
    text.style.whiteSpace = 'pre-wrap';
    detail.append(text, analysisElement('p', 'analysis-section-help',
      `取込本文: ${row.original_text ?? '対応する取込本文なし'} / 時刻: ${row.start ?? '不明'}–${row.end ?? '不明'}`));
    const fields = analysisElement('div', 'analysis-settings-grid');
    fields.append(
      control('本文確認', 'text_status', {unreviewed: '未確認', transcript_checked: '逐語録を確認（音声未照合）', audio_verified: '音声・動画と照合済み', unclear: '聞き取り不明・要確認'}, row.segment_id),
      control('役割（初期値は不明）', 'role', {unknown: '不明', participant: '参加者', moderator: '司会者', observer: '観察者'}, row.segment_id),
      control('発言者を確認した', 'speaker_verified', 'checkbox', row.segment_id),
      control('一人の発言として区切りを確認した', 'boundary_verified', 'checkbox', row.segment_id),
      control('元資料の位置（行・ページ等）', 'source_locator', 'text', row.segment_id),
      control('分割・結合元の発言ID（カンマ区切り。不明は空欄）', 'source_segment_ids', 'text', row.segment_id)
    );
    detail.append(fields);
    turns.append(detail);
  });
  panel.body.append(turns);
  if (prepared.analysis_needs_review) panel.body.append(control(
    '現在の版で既存のコード・相互作用を研究者が再確認した（明示的に解除）', 'review_analysis', 'checkbox'));
  const message = analysisElement('p', 'analysis-section-help');
  message.setAttribute('role', 'status');
  for (const [label, confirm] of [['確認途中として保存', false], ['本文・区切りを確認して版を確定', true]]) {
    const button = analysisElement('button', 'secondary-button', label);
    button.type = 'button';
    button.dataset.preparationSave = String(confirm);
    button.addEventListener('click', async () => {
      if (preparationSaving) return;
      if (analysisState.dirty) {
        message.textContent = '先に未保存の分析設定・コードを保存してください。';
        return;
      }
      const itemId = analysisState.itemId;
      const payload = {...deepCopy(preparationDraft), confirm};
      const sent = JSON.stringify(preparationDraft);
      preparationSaving = true;
      message.textContent = '保存中…';
      try {
        const response = await apiFetch(`/api/library/${encodeURIComponent(itemId)}/preparation`, {
          method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
        });
        const result = await readJsonResponse(response);
        if (!response.ok) throw new Error(result.error || '準備記録を保存できませんでした。');
        if (analysisState.itemId !== itemId) return;
        if (JSON.stringify(preparationDraft) !== sent) {
          preparationDraft.revision = result.revision;
          message.textContent = '保存しました。保存中の追加編集があるため、もう一度保存してください。';
          return;
        }
        preparationDirty = false;
        await loadAnalysisItem(itemId, {discardDirty: true});
        setAlert(document.querySelector('#analysis-message'), '準備記録を保存しました。話者・順序の不足は別途表示されます。');
      } catch (error) {
        message.textContent = error.message;
      } finally {
        preparationSaving = false;
      }
    });
    panel.body.append(button);
  }
  panel.body.append(message);
  return panel.panel;
}

function qualitativeCount(value) {
  const count = Number(value);
  return Number.isFinite(count) ? Math.max(0, Math.floor(count)) : 0;
}

function qualitativeEvidenceDetails(segments, {continuous = false} = {}) {
  const details = analysisElement('details', 'qualitative-evidence');
  details.append(analysisElement('summary', '', continuous
    ? `根拠の連続発言を開く（${segments.length}発言・両端とその間）`
    : `該当発言を開く（${segments.length}発言・連続ではない抜粋）`));
  const list = analysisElement('div', 'qualitative-evidence-list');
  const reviews = new Map((analysisState.data.manual?.preparation?.rows || []).map(row => [row.segment_id, row]));
  const codes = new Map((analysisState.data.manual?.codebook || []).map(code => [code.id, code]));
  let offset = 0;
  const more = contentButton('次の40発言を表示', appendNext);
  function appendNext() {
    const batch = segments.slice(offset, offset + 40);
    offset += batch.length;
    batch.forEach(segment => {
      const review = reviews.get(segment.id);
      const textStatus = {unreviewed: '未確認', transcript_checked: '逐語録確認済み・音声未照合',
        audio_verified: '音声照合済み', unclear: '聞き取り不明'}[review?.text_status] || '不明';
      const role = {participant: '参加者', moderator: '司会者', observer: '観察者'}[review?.role] || '役割不明';
      const article = analysisElement('blockquote', 'qualitative-quote');
      article.dataset.qualitativeEvidenceId = segment.id;
      article.append(analysisElement('p', 'qualitative-exact-text', segment.text || '（本文なし）'));
      article.append(analysisElement('p', 'analysis-caption',
        `#${segment.utterance_order ?? '不明'} / ${segment.speaker_name || segment.speaker || '話者不明'} / ${role} / ${segment.id}`));
      article.append(analysisElement('p', 'analysis-caption',
        `本文確認: ${textStatus} / 話者・役割・順序: ${review?.interaction_ready ? '準備記録で確認済み' : '未確認項目あり'}${segment.excluded ? ' / 集計から除外（文脈として表示）' : ''}`));
      const labels = (segment.annotation?.codes || []).map(id => codes.get(id)).filter(Boolean)
        .map(code => [code.label, code.category && `カテゴリー: ${code.category}`, code.theme && `テーマ: ${code.theme}`].filter(Boolean).join(' / '));
      if (labels.length) article.append(analysisElement('p', 'analysis-caption', `内容のコード: ${labels.join('；')}`));
      if (segment.valid_time) article.append(contentButton('元の発言・音声を確認', () => openInsightMedia(segment)));
      else article.append(analysisElement('p', 'analysis-caption', '時刻不明のため音声位置への移動はできません。'));
      list.insertBefore(article, more);
    });
    more.hidden = offset >= segments.length;
  }
  list.append(more);
  details.append(list);
  details.addEventListener('toggle', () => { if (details.open && !offset) appendNext(); });
  return details;
}

function renderInteractionTimeline() {
  const panel = analysisCardPanel('相互作用と意見変化の発言順タイムライン', 'manual', 'interaction_links', true, 'qualitative_coding');
  panel.panel.dataset.interactionTimeline = '';
  const data = analysisState.data;
  const manual = data.manual || {};
  const segments = data.segments || [];
  const lookup = new Map(segments.map((segment, index) => [segment.id, {segment, index}]));
  const links = (manual.interaction_links || []).slice().sort((a, b) =>
    (lookup.get(a.source_segment_id)?.index ?? Infinity) - (lookup.get(b.source_segment_id)?.index ?? Infinity));
  const stale = Boolean(manual.preparation?.analysis_needs_review);
  panel.body.append(analysisElement('p', 'analysis-section-help',
    '保存済みの手動リンクを、応答した発言の順で表示します。矢印は「参照先 → 応答発言」で、因果関係や同調圧力を示しません。間隔は経過時間を表しません。'));
  panel.body.append(analysisElement('p', 'analysis-caption',
    `入力版: ${manual.preparation?.input_version ?? '未固定'} / ${links.length}リンク。リンク件数は支持人数ではありません。意見変更などの判定は研究者の解釈です。`));
  if (stale) panel.body.append(analysisElement('p', 'analysis-orphan-warning',
    '要再確認：根拠の版が変わっています。旧リンクのIDのみ表示し、現在の本文を旧解釈の根拠として結びません。'));
  if (!links.length) {
    panel.body.append(analysisElement('p', 'analysis-no-data', '相互作用リンクは未登録です。「発話ごとのコード・相互作用・メモ」で対象発言と関係を指定して保存すると表示されます。'));
    return panel.panel;
  }
  const filter = document.createElement('select');
  filter.dataset.interactionFilter = '';
  filter.append(new Option('すべての関係', ''));
  const relations = new Map(links.map(link => [link.relation, link.relation_label || link.relation]));
  relations.forEach((label, id) => filter.append(new Option(label, id)));
  panel.body.append(analysisField('関係の種類で絞り込み', filter));
  const count = analysisElement('p', 'analysis-caption');
  count.setAttribute('aria-live', 'polite');
  const list = analysisElement('ol', 'qualitative-timeline');
  let offset = 0;
  let filtered = links;
  const more = contentButton('次の30リンクを表示', appendNext);
  more.dataset.interactionMore = '';
  function appendNext() {
    const batch = filtered.slice(offset, offset + 30);
    offset += batch.length;
    batch.forEach(link => {
      const from = lookup.get(link.target_segment_id);
      const to = lookup.get(link.source_segment_id);
      const unavailable = stale || link.analysis_needs_review || link.status === 'missing_target' || !from || !to;
      const event = analysisElement('li', `qualitative-event${unavailable ? ' needs-review' : ''}`);
      event.dataset.interactionSource = link.source_segment_id;
      event.dataset.interactionRelation = link.relation;
      event.append(analysisElement('strong', 'qualitative-relation', link.relation_label || link.relation));
      if (unavailable) {
        event.append(analysisElement('p', '', `${link.target_segment_id} → ${link.source_segment_id}`));
        event.append(analysisElement('p', 'analysis-caption', !from || !to || link.status === 'missing_target'
          ? '参照先の発言がありません。履歴・JSONを確認してください。'
          : '根拠が要再確認です。準備画面で現在の版との対応を確認してください。'));
      } else {
        const pair = analysisElement('div', 'qualitative-response-pair');
        [from.segment, to.segment].forEach((segment, index) => {
          if (index) pair.append(analysisElement('span', 'qualitative-direction', '応答'));
          const endpoint = analysisElement('div', 'qualitative-endpoint');
          endpoint.append(analysisElement('strong', '', `#${segment.utterance_order ?? '不明'} ${segment.speaker_name || segment.speaker || '話者不明'}`));
          const excerpt = segment.text || '';
          endpoint.append(analysisElement('p', 'qualitative-exact-text', excerpt.length > 160 ? `${excerpt.slice(0, 160)}…（全文は下の根拠）` : excerpt));
          pair.append(endpoint);
        });
        event.append(pair);
        const first = Math.min(from.index, to.index), last = Math.max(from.index, to.index);
        event.append(qualitativeEvidenceDetails(segments.slice(first, last + 1), {continuous: true}));
      }
      if (link.evidence_memo) event.append(analysisElement('p', 'qualitative-interpretation', `研究者の解釈メモ: ${link.evidence_memo}`));
      list.append(event);
    });
    count.textContent = `${filtered.length}リンク中 ${offset}リンクを表示（全体 ${links.length}リンク）`;
    more.hidden = offset >= filtered.length;
  }
  filter.addEventListener('change', () => {
    filtered = links.filter(link => !filter.value || link.relation === filter.value);
    offset = 0;
    list.replaceChildren();
    appendNext();
  });
  panel.body.append(count, list, more);
  appendNext();
  return panel.panel;
}

function renderManualSummary(container, compact) {
  const manual = analysisState.data.manual || {};
  container.append(analysisElement('p', 'analysis-caption qualitative-snapshot-notice',
    manual.preparation?.analysis_needs_review
      ? '要再確認：以下のコード集計・比較表には以前の解釈が含まれます。現在の入力に対する確定結果ではありません。'
      : '図表は保存済みの分析記録です。未保存のコード・リンクの編集は、保存後に反映されます。'));
  const checks = Array.isArray(manual.context_checks) ? manual.context_checks : [];
  const readiness = analysisCardPanel('分析前の確認', 'configured', 'context');
  const checkGrid = analysisElement('div', 'analysis-check-grid');
  checks.forEach(item => {
    const row = analysisElement('div', item.ready ? 'ready' : 'missing');
    row.append(
      analysisElement('span', '', item.ready ? '✓' : '!'),
      analysisElement('strong', '', item.label),
      analysisElement('small', '', item.ready ? '設定済み' : '要設定')
    );
    checkGrid.append(row);
  });
  readiness.body.append(checkGrid);
  container.append(readiness.panel);

  const plan = manual.focus_group_plan || {};
  if (plan && Object.keys(plan).length) {
    const planPanel = analysisCardPanel('対象データの確認と分析方針', 'configured', 'analysis_plan', true);
    planPanel.body.append(
      analysisElement('p', 'analysis-section-help', `${plan.status || '不明'}：${plan.provisional_assumption || ''}`)
    );
    const inventory = Array.isArray(plan.data_inventory) ? plan.data_inventory : [];
    const missing = inventory.filter(item => item.status === '不明' || item.status === '一部');
    if (missing.length) {
      const list = analysisElement('ul', 'analysis-inline-list');
      missing.forEach(item => list.append(analysisElement('li', '', `${item.item}: ${item.value}`)));
      planPanel.body.append(analysisElement('strong', '', '要確認'), list);
    }
    const methods = Array.isArray(plan.methods) ? plan.methods : [];
    methods.forEach(item => planPanel.body.append(analysisElement(
      'p', 'analysis-list-row', `${item.role}：${item.method}（データ充足: ${item.data_sufficiency}）`
    )));
    const expertBlock = analysisState.data.experts || {};
    if (expertBlock.status === 'unavailable') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', expertBlock.message || '専門家定義を読み込めません。'));
    }
    (Array.isArray(expertBlock.experts) ? expertBlock.experts : []).forEach(expert => {
      planPanel.body.append(buildExpertDetails(expert));
    });
    if (expertBlock.ai && expertBlock.ai.mode === 'blocked') {
      planPanel.body.append(analysisElement('p', 'analysis-section-help', `AI見解：${expertBlock.ai.reason}`));
    }
    container.append(planPanel.panel);
  }

  const codeMetrics = Array.isArray(manual.code_metrics) ? manual.code_metrics : [];
  const interactionSummary = Array.isArray(manual.interaction_summary) ? manual.interaction_summary : [];
  if (codeMetrics.length || interactionSummary.some(item => item.count)) {
    const summary = analysisCardPanel('手動コードの集計', 'manual', 'codes', true, 'qualitative_coding');
    if (codeMetrics.length) {
      const maximum = codeMetrics.reduce((max, item) => Math.max(max, qualitativeCount(item.segment_count)), 0);
      summary.body.append(analysisElement('p', 'analysis-caption',
        `棒の共通尺度: 0～${maximum}発言（最長の棒＝最大件数）。割合・重要性・支持人数を表しません。同一発言への同一コードは1件、複数コードはそれぞれに計上します。`));
      codeMetrics.forEach(item => {
        const value = qualitativeCount(item.segment_count);
        const row = appendAnalysisBar(summary.body, item.label, maximum ? 100 * value / maximum : 0,
          `${value}発言 / ${qualitativeCount(item.speaker_count)}話者ラベル / ${item.group_count ?? '不明'}グループ / 重要引用 ${qualitativeCount(item.important_count)}件 / ${analysisObservedTimeText(item)}`, item.color);
        row.dataset.qualitativeCode = item.id;
        row.querySelector('.analysis-bar-track').setAttribute('aria-label', `${item.label}: ${value}発言。共通尺度0～${maximum}発言`);
        row.querySelector('.analysis-bar-track i').style.minWidth = '0';
      });
    }
    const tags = analysisElement('div', 'analysis-interaction-summary');
    interactionSummary.filter(item => item.count).forEach(item => {
      const chip = analysisElement('span', '', `${item.label} ${item.count}件`);
      tags.append(chip);
    });
    if (tags.childNodes.length) summary.body.append(tags);
    container.append(summary.panel);
  }

  const matrix = Array.isArray(manual.case_code_matrix) ? manual.case_code_matrix : [];
  const codebook = Array.isArray(manual.codebook) ? manual.codebook : [];
  if (matrix.length && codebook.length) {
    const matrixPanel = analysisCardPanel('話者×コード（発言件数）', 'manual', 'case_matrix', true, 'qualitative_coding');
    const wrap = analysisElement('div', 'analysis-table-wrap');
    wrap.tabIndex = 0;
    wrap.setAttribute('role', 'region');
    wrap.setAttribute('aria-label', '話者×コード比較表。列が多い場合は横にスクロールできます。');
    const table = analysisElement('table', 'analysis-table analysis-matrix');
    const maximum = matrix.reduce((max, row) => (row.codes || []).reduce(
      (value, code) => Math.max(value, qualitativeCount(code.count)), max), 0);
    matrixPanel.body.append(analysisElement('p', 'analysis-caption', `色の共通尺度: 0～${maximum}発言。件数を押すと該当する発言を開けます。話者ラベルと実際の人数は別です。`));
    const evidence = analysisElement('div', 'qualitative-matrix-evidence');
    evidence.setAttribute('aria-live', 'polite');
    const head = analysisElement('thead');
    const headRow = analysisElement('tr');
    headRow.append(analysisElement('th', '', '話者'));
    codebook.forEach(code => {
      const cell = analysisElement('th', '', code.label);
      cell.scope = 'col';
      headRow.append(cell);
    });
    head.append(headRow);
    const body = analysisElement('tbody');
    matrix.forEach(rowData => {
      const row = analysisElement('tr');
      row.append(analysisElement('th', '', rowData.speaker_name || rowData.speaker));
      const counts = new Map((rowData.codes || []).map(item => [item.code_id, item.count]));
      codebook.forEach(code => {
        const value = qualitativeCount(counts.get(code.id));
        const cell = analysisElement('td', value ? 'has-value' : '');
        cell.style.setProperty('--matrix-strength', String(maximum ? value / maximum : 0));
        if (value) {
          const button = contentButton(String(value), () => {
            evidence.replaceChildren(analysisElement('strong', '', `${rowData.speaker_name || rowData.speaker} × ${code.label}`));
            if (manual.preparation?.analysis_needs_review) {
              evidence.append(analysisElement('p', '', '要再確認：現在の本文を旧コードの根拠として表示できません。'));
              return;
            }
            const matching = (analysisState.data.segments || []).filter(segment => !segment.excluded
              && segment.speaker === rowData.speaker && (segment.annotation?.codes || []).includes(code.id));
            const details = qualitativeEvidenceDetails(matching);
            evidence.append(details);
            details.open = true;
            details.querySelector('summary').focus();
          }, 'qualitative-matrix-button');
          button.setAttribute('aria-label', `${rowData.speaker_name || rowData.speaker}、${code.label}、${value}発言の根拠を開く`);
          cell.append(button);
        } else cell.textContent = '0';
        row.append(cell);
      });
      body.append(row);
    });
    table.append(head, body);
    wrap.append(table);
    matrixPanel.body.append(wrap, evidence);
    container.append(matrixPanel.panel);
  }
  container.append(renderInteractionTimeline());
}

function renderManualAnalysis(compact) {
  const fragment = document.createDocumentFragment();
  const manual = (analysisState.data && analysisState.data.manual) || {};
  const intro = analysisElement('div', 'analysis-result-intro manual');
  intro.append(
    analysisElement('span', 'analysis-kind manual', '要設定・要確認'),
    analysisElement('h2', '', compact ? '設定・手動分析' : '研究目的に沿った設定と手動コーディング'),
    analysisElement('p', '', 'テーマ、合意・対立、沈黙の意味は自動確定できません。定義を作り、発話を読み、根拠と解釈を保存してください。')
  );
  fragment.append(intro);
  fragment.append(renderTranscriptPreparation());
  const orphanedCount = Number(manual.orphaned_annotation_count) || 0;
  if (orphanedCount > 0) {
    const warning = analysisElement('div', 'analysis-orphan-warning');
    warning.setAttribute('role', 'status');
    warning.append(
      analysisElement('strong', '', '参照先のない注釈があります'),
      analysisElement('p', '', `文字起こし編集で参照先がなくなった注釈が${orphanedCount}件あります。JSONには復旧用に保持されています。`)
    );
    fragment.append(warning);
  }

  const summaryGrid = analysisElement('div', 'analysis-grid manual-summary-grid');
  renderManualSummary(summaryGrid, compact);
  const importantQuotes = (analysisState.data.segments || []).filter(segment => {
    const annotation = analysisState.annotations[segment.id] || {};
    return annotation.important && !annotation.excluded;
  });
  if (importantQuotes.length) {
    const quotesPanel = analysisCardPanel('重要引用', 'manual', 'important_quotes', true, 'qualitative_coding');
    importantQuotes.slice(0, compact ? 5 : 12).forEach(segment => {
      const quote = analysisElement('blockquote', 'analysis-important-quote');
      quote.append(
        analysisElement('p', '', segment.text || '（本文なし）'),
        analysisElement('footer', '', `${segment.speaker_name || segment.speaker} / ${formatTime(segment.start || 0)}–${formatTime(segment.end || 0)}`)
      );
      quotesPanel.body.append(quote);
    });
    summaryGrid.append(quotesPanel.panel);
  }
  summaryGrid.append(analysisExportDirectory('手動分析データの出力', 'manual', [
    ['report', '分析レポート（Markdown）'],
    ['analysis_plan', '分析方針・データ確認 CSV'],
    ['analysis_units', '発言と分析結果の対応表 CSV'],
    ['context', '入力・確認状況 CSV'],
    ['codes', 'コード集計 CSV'],
    ['codebook_history', 'コードブック変更履歴 CSV'],
    ['coded_segments', 'コード済み発話 CSV'],
    ['interactions', '相互作用タグ CSV'],
    ['interaction_links', '相互作用の根拠発話 CSV'],
    ['case_matrix', '話者×コード CSV'],
    ['important_quotes', '重要引用 CSV']
  ]));
  fragment.append(summaryGrid);

  const settingsPanel = analysisCardPanel('分析条件', 'configured', '', true);
  const settingsGrid = analysisElement('div', 'analysis-settings-grid');
  settingsGrid.append(
    analysisField('研究質問', analysisConfigControl('research_question', 'textarea'), '分析で明らかにしたい問いを記録します。'),
    analysisField('主となる分析手法', analysisConfigControl('analysis_method', 'select', {
      auto: '資料に応じて暫定選定', qualitative_content: '質的内容分析', thematic: 'テーマ分析',
      framework: 'フレームワーク分析', scat: 'SCAT', mgta: 'M-GTA', kj: 'KJ法',
      quantitative_text: '計量テキスト分析（補助）', interaction: '相互作用分析'
    }), '分析方針・データ確認CSVで、必要な手順と不足資料を確認できます。'),
    analysisField('手法選定の理由', analysisConfigControl('method_rationale', 'textarea'), '研究目的・データとの対応、得たい結果、限界を研究者が記録します。'),
    analysisField('分析単位', analysisConfigControl('analysis_unit', 'select', {
      turn: '発話単位'
    })),
    analysisField(
      '比較軸',
      analysisConfigControl('group_by', 'select', analysisGroupByOptions()),
      '話者管理とリンク済みの事前アンケート項目も回答群ごとの比較に使えます。'
    ),
    analysisField('長い無音の基準（秒）', analysisConfigControl('long_gap_seconds', 'number')),
    analysisField('重なり候補の基準（秒）', analysisConfigControl('overlap_seconds', 'number')),
    analysisField('低参加候補の基準（%）', analysisConfigControl('low_participation_percent', 'number')),
    analysisField('時間帯の幅（秒）', analysisConfigControl('time_bin_seconds', 'number')),
    analysisField('特徴語から除外する語', analysisConfigControl('stop_words', 'text'), 'カンマ区切りで入力します。'),
    analysisField('Sudachi分割単位', analysisConfigControl('morph_split_mode', 'select', {
      A: 'A（短単位）', B: 'B（中間）', C: 'C（長単位・既定）'
    }), 'GiNZA利用時はモデル側の設定を記録します。'),
    analysisField('共起の最小発話数', analysisConfigControl('cooccurrence_min_count', 'number')),
    analysisField('共起へ使う上位語数', analysisConfigControl('cooccurrence_top_terms', 'number')),
    analysisField('統計の比較軸', analysisConfigControl('statistics_group_by', 'select', {
      speaker: '話者', role: '会話役割'
    }), '同一会話内の発話は独立でない可能性があります。')
  );
  const excludeModerator = analysisElement('label', 'check-row analysis-setting-check');
  excludeModerator.append(
    analysisConfigControl('exclude_moderator', 'checkbox'),
    analysisElement('span', '', '参加バランスから司会・観察役を除外する')
  );
  settingsGrid.append(excludeModerator);
  settingsPanel.body.append(settingsGrid, analysisTermCrosstabSelector(compact));

  const speakerExclusions = analysisElement('fieldset', 'analysis-speaker-exclusions');
  speakerExclusions.append(analysisElement('legend', '', '分析から除外する話者'));
  const uniqueSpeakers = new Map();
  (analysisState.data.segments || []).forEach(segment => {
    if (!uniqueSpeakers.has(segment.speaker)) uniqueSpeakers.set(segment.speaker, segment.speaker_name || segment.speaker);
  });
  uniqueSpeakers.forEach((name, speaker) => {
    const label = analysisElement('label');
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.checked = (analysisState.config.excluded_speakers || []).includes(speaker);
    input.dataset.analysisExcludedSpeaker = speaker;
    label.append(input, analysisElement('span', '', name));
    speakerExclusions.append(label);
  });
  settingsPanel.body.append(speakerExclusions);
  fragment.append(settingsPanel.panel);

  const codebookPanel = analysisCardPanel('コードブック', 'configured', '', true, 'qualitative_coding');
  codebookPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'コードの意味と含む／含まない例、カテゴリー、テーマを先に定義すると、複数人でも判断を揃えやすくなります。'),
    analysisField('今回のコードブック変更理由', analysisConfigControl('codebook_change_reason', 'textarea'), '追加・修正・削除の理由を記入します。変更時に履歴へ保存されます。'),
    analysisCodebookEditor(compact)
  );
  fragment.append(codebookPanel.panel);

  const codingPanel = analysisCardPanel('発話ごとのコード・相互作用・メモ', 'manual', 'coded_segments', true, 'qualitative_coding');
  codingPanel.body.append(
    analysisElement('p', 'analysis-section-help', 'タグは観察記録です。合意や発言抑制などの意味は、前後の発話や音声を確認して設定してください。'),
    analysisCodingWorkspace(compact)
  );
  fragment.append(codingPanel.panel);

  const interpretationPanel = analysisCardPanel('研究者の解釈', 'manual', '', true);
  const interpretationGrid = analysisElement('div', 'analysis-interpretation-grid');
  interpretationGrid.append(
    analysisField('分析メモ', analysisConfigControl('analyst_memo', 'textarea'), 'テーマ、例外事例、少数意見、次に確認する点を記録します。'),
    analysisField('確認状態', analysisConfigControl('interpretation_status', 'select', {
      draft: '下書き・要確認', reviewed: '確認済み'
    }))
  );
  interpretationPanel.body.append(interpretationGrid);
  fragment.append(interpretationPanel.panel);

  const saveBar = analysisElement('div', 'analysis-save-bar');
  const saveText = analysisElement('div');
  saveText.append(
    analysisElement('strong', '', analysisState.dirty ? '未保存の変更があります' : '分析設定は保存済みです'),
    analysisElement('span', '', '保存すると自動集計とExcel・CSV・JSONも更新されます。')
  );
  saveText.firstElementChild.dataset.analysisSaveState = 'true';
  const save = analysisElement('button', 'primary-button small', analysisState.dirty ? '設定とコードを保存' : '保存済み');
  save.type = 'button';
  save.dataset.analysisSave = 'true';
  save.disabled = !analysisState.dirty;
  saveBar.append(saveText, save);
  fragment.append(saveBar);
  return fragment;
}

function syncAnalysisControls(source, selector, predicate) {
  document.querySelectorAll(selector).forEach(control => {
    if (control === source || !predicate(control)) return;
    if (source.type === 'checkbox') control.checked = source.checked;
    else control.value = source.value;
  });
}

function updateAnalysisConfigFromControl(control) {
  const field = control.dataset.analysisConfig;
  if (!field) return false;
  let value;
  if (control.type === 'checkbox') value = control.checked;
  else if (control.type === 'number') {
    const number = Number(control.value);
    value = Number.isFinite(number) ? number : analysisState.config[field];
  } else if (field === 'stop_words' || field === 'crosstab_terms') {
    value = control.value.split(/[,、\n]/).map(item => item.trim()).filter(Boolean);
  } else value = control.value;
  analysisState.config[field] = value;
  syncAnalysisControls(control, '[data-analysis-config]', peer => peer.dataset.analysisConfig === field);
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisCodeFromControl(control) {
  const codeId = control.dataset.analysisCodeId;
  const field = control.dataset.analysisCodeField;
  if (!codeId || !field) return false;
  const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
  const code = codebook.find(item => item.id === codeId);
  if (!code) return false;
  code[field] = field === 'color' ? safeAnalysisColor(control.value) : control.value;
  syncAnalysisControls(control, '[data-analysis-code-id]', peer => (
    peer.dataset.analysisCodeId === codeId && peer.dataset.analysisCodeField === field
  ));
  setAnalysisDirty(true);
  return true;
}

function updateAnalysisAnnotationFromControl(control) {
  const segmentId = control.dataset.analysisSegmentId;
  const field = control.dataset.analysisAnnotationField;
  if (!segmentId || !field) return false;
  const annotation = analysisAnnotation(segmentId);
  const itemValue = control.dataset.analysisAnnotationValue;
  if (field === 'codes' || field === 'interaction_tags') {
    const values = Array.isArray(annotation[field]) ? annotation[field] : [];
    annotation[field] = control.checked
      ? [...new Set([...values, itemValue])]
      : values.filter(value => value !== itemValue);
  } else if (field === 'important' || field === 'excluded') annotation[field] = control.checked;
  else if (['importance_score', 'review_score', 'sensitivity_score'].includes(field)) {
    const number = control.value === '' ? null : Number(control.value);
    annotation[field] = Number.isFinite(number) ? Math.max(0, Math.min(100, Math.round(number))) : null;
  }
  else annotation[field] = control.value;
  syncAnalysisControls(control, '[data-analysis-annotation-field]', peer => (
    peer.dataset.analysisSegmentId === segmentId
    && peer.dataset.analysisAnnotationField === field
    && peer.dataset.analysisAnnotationValue === itemValue
  ));
  setAnalysisDirty(true);
  return true;
}

function refreshAnalysisSegmentLists() {
  document.querySelectorAll('[data-analysis-segment-list]').forEach(list => {
    renderAnalysisSegmentItems(list, list.dataset.analysisSegmentList === 'mobile');
  });
}

async function saveAnalysis() {
  if (!analysisState.itemId || !analysisState.data || analysisSaveInProgress) return;
  const saveContext = captureAnalysisContext();
  analysisSaveOwner = saveContext;
  // Preserve later edits only within this same data/navigation/revision owner.
  const ownsSave = () => analysisSaveOwner === saveContext
    && isAnalysisContextCurrent({...saveContext, mutation: analysisMutationGeneration});
  analysisSaveInProgress = true;
  setAnalysisDirty(true, false);
  setAlert(document.querySelector('#analysis-message'), '');
  const savedItemId = analysisState.itemId;
  const saveGeneration = analysisMutationGeneration;
  try {
    const item = analysisState.data.item || {};
    const response = await apiFetch(`/api/library/${encodeURIComponent(savedItemId)}/analysis`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_revision: Number(item.revision_count || 0),
        analysis_revision: Number(item.analysis_revision || 0),
        config: analysisState.config,
        annotations: analysisState.annotations
      })
    });
    const payload = await readJsonResponse(response);
    if (!ownsSave()) return;
    if (!response.ok) throw new Error(payload.error || '分析設定を保存できませんでした。');
    const data = payload.analysis && typeof payload.analysis === 'object' ? payload.analysis : payload;
    analysisSaveInProgress = false;
    const hasLaterChanges = analysisState.itemId === savedItemId
      && analysisMutationGeneration !== saveGeneration;
    if (analysisState.itemId === savedItemId && !hasLaterChanges) {
      analysisState.data = data;
      invalidateAnalysisMethodOverview();
      analysisState.config = deepCopy(data.config || {});
      analysisState.annotations = deepCopy(data.annotations || {});
      if (analysisTermRunRequested) analysisState.mode = 'automatic';
      analysisTermRunRequested = false;
      setAnalysisDirty(false);
      renderAnalysisWorkspace();
      onContentAnalysisLoaded();
      setAlert(document.querySelector('#analysis-message'), '分析設定、手動コード、解釈メモを保存し、集計と出力データを更新しました。');
    } else if (analysisState.itemId === savedItemId) {
      if (analysisState.data && analysisState.data.item && data.item) {
        analysisState.data.item.revision_count = data.item.revision_count;
        analysisState.data.item.analysis_revision = data.item.analysis_revision;
        analysisState.data.item.analysis_updated_at = data.item.analysis_updated_at;
      }
      setAnalysisDirty(true, false);
      setAlert(document.querySelector('#analysis-message'), '保存開始後の追加変更が残っています。内容を確認して、もう一度保存してください。', true);
    }
    if (typeof analysisMeasurementRefreshContext === 'function') analysisMeasurementRefreshContext();
  } catch (error) {
    if (!ownsSave()) return;
    analysisSaveInProgress = false;
    analysisTermRunRequested = false;
    setAnalysisDirty(true, false);
    setAlert(document.querySelector('#analysis-message'), error.message, true);
  } finally {
    // An old completion must not release a newer view's save operation.
    if (analysisSaveOwner === saveContext) {
      analysisSaveOwner = null;
      analysisSaveInProgress = false;
      analysisTermRunRequested = false;
      setAnalysisDirty(analysisState.dirty, false);
    }
  }
}

listen(analysisItemSelect, 'change', () => loadAnalysisItem(analysisItemSelect.value));
listen(document.querySelector('#analysis-refresh-button'), 'click', () => {
  if (!analysisState.itemId) return;
  if (hasUnsavedAnalysisChanges() && !window.confirm('未保存の分析設定・手動コード・準備記録を破棄して再集計しますか？')) return;
  loadAnalysisItem(analysisState.itemId, {discardDirty: true});
});

listen(analysisCard, 'click', event => {
  const runClassification = event.target.closest('[data-run-segment-classification]');
  if (runClassification) {
    runSegmentClassification();
    return;
  }
  const applyClassification = event.target.closest('[data-apply-classification-proposal]');
  if (applyClassification) {
    const segmentId = applyClassification.dataset.analysisSegmentId;
    const result = ((analysisState.data || {}).segment_classification || {}).result || {};
    const row = (result.segments || []).find(value => String(value.segment_id) === String(segmentId));
    const source = row && row[applyClassification.dataset.applyClassificationProposal];
    if (source) {
      const annotation = analysisAnnotation(segmentId);
      annotation.dialogue_act = source.dialogue_act || '';
      annotation.importance_score = source.importance_score ?? null;
      annotation.review_score = source.review_score ?? null;
      annotation.sensitivity_score = source.sensitivity_score ?? null;
      annotation.classification_status = 'draft';
      setAnalysisDirty(true);
      renderAnalysisWorkspace();
    }
    return;
  }
  const scope = event.target.closest('[data-analysis-scope]');
  if (scope) {
    analysisState.automaticScope = scope.dataset.analysisScope === 'speakers' ? 'speakers' : 'overall';
    renderAnalysisWorkspace();
    return;
  }
  const selectedSpeaker = event.target.closest('[data-analysis-speaker-id]');
  if (selectedSpeaker) {
    analysisState.selectedSpeaker = selectedSpeaker.dataset.analysisSpeakerId || '';
    const mobile = window.matchMedia('(max-width: 959px)').matches;
    renderAnalysisWorkspace();
    if (mobile) {
      window.requestAnimationFrame(() => {
        const detail = analysisCard.querySelector('.analysis-mobile-layout .analysis-speaker-detail');
        if (!detail) return;
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        detail.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
      });
    }
    return;
  }
  const jump = event.target.closest('[data-analysis-jump]');
  if (jump) {
    const content = jump.closest('.analysis-content');
    if (content?.querySelector('[data-analysis-page]')) {
      selectAnalysisPage(jump.dataset.analysisJump);
      return;
    }
    const target = content && content.querySelector(`[data-analysis-anchor="${jump.dataset.analysisJump}"]`);
    if (target) {
      content.querySelectorAll('[data-analysis-jump]').forEach(button => {
        const active = button === jump;
        button.classList.toggle('active', active);
        button.setAttribute('aria-current', active ? 'true' : 'false');
      });
      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      target.scrollIntoView({behavior: reducedMotion ? 'auto' : 'smooth', block: 'start'});
    }
    return;
  }
  const mode = event.target.closest('[data-analysis-mode]');
  if (mode) {
    setAnalysisMode(mode.dataset.analysisMode);
    return;
  }
  const methodSelect = event.target.closest('[data-analysis-method-select]');
  if (methodSelect) {
    analysisMethodState().selected = methodSelect.dataset.analysisMethodSelect;
    renderAnalysisWorkspace();
    return;
  }
  if (event.target.closest('[data-analysis-methods-refresh]')) {
    invalidateAnalysisMethodOverview();
    renderAnalysisWorkspace();
    return;
  }
  const save = event.target.closest('[data-analysis-save]');
  if (save) {
    saveAnalysis();
    return;
  }
  const runTermCrosstab = event.target.closest('[data-analysis-run-term-crosstab]');
  if (runTermCrosstab) {
    const terms = Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : [];
    if (!terms.length) {
      setAlert(document.querySelector('#analysis-message'), '検定する単語を1つ以上入力または選択してください。', true);
      return;
    }
    analysisTermRunRequested = true;
    saveAnalysis();
    return;
  }
  const termChoice = event.target.closest('[data-analysis-crosstab-term]');
  if (termChoice) {
    const term = String(termChoice.dataset.analysisCrosstabTerm || '').trim();
    const selected = new Set(Array.isArray(analysisState.config.crosstab_terms) ? analysisState.config.crosstab_terms : []);
    if (selected.has(term)) selected.delete(term);
    else if (selected.size < 30) selected.add(term);
    analysisState.config.crosstab_terms = [...selected];
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    return;
  }
  const addInteractionLink = event.target.closest('[data-analysis-add-interaction-link]');
  if (addInteractionLink) {
    const sourceId = addInteractionLink.dataset.analysisAddInteractionLink;
    const bySource = (attribute) => [...addInteractionLink.closest('.analysis-segment-card').querySelectorAll(`[${attribute}]`)]
      .find(control => control.getAttribute(attribute) === sourceId);
    const target = bySource('data-analysis-interaction-target');
    const relation = bySource('data-analysis-interaction-relation');
    const memo = bySource('data-analysis-interaction-memo');
    if (!target || !target.value || !relation || !relation.value) {
      setAlert(document.querySelector('#analysis-message'), '対象発話と関係を選択してください。', true);
      return;
    }
    const annotation = analysisAnnotation(sourceId);
    const links = Array.isArray(annotation.interaction_links) ? annotation.interaction_links : [];
    const candidate = {
      target_segment_id: target.value,
      relation: relation.value,
      evidence_memo: memo ? memo.value.trim() : ''
    };
    const duplicate = links.some(link => link.target_segment_id === candidate.target_segment_id
      && link.relation === candidate.relation && link.evidence_memo === candidate.evidence_memo);
    if (!duplicate) annotation.interaction_links = [...links, candidate];
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    return;
  }
  const removeInteractionLink = event.target.closest('[data-analysis-remove-interaction-link]');
  if (removeInteractionLink) {
    const sourceId = removeInteractionLink.dataset.analysisInteractionSource;
    const index = Number(removeInteractionLink.dataset.analysisInteractionIndex);
    const annotation = analysisAnnotation(sourceId);
    if (Number.isInteger(index) && index >= 0) {
      annotation.interaction_links = (annotation.interaction_links || []).filter((_, position) => position !== index);
      setAnalysisDirty(true);
      renderAnalysisWorkspace();
    }
    return;
  }
  const addCode = event.target.closest('[data-analysis-add-code]');
  if (addCode) {
    const codebook = Array.isArray(analysisState.config.codebook) ? analysisState.config.codebook : [];
    const id = self.crypto && self.crypto.randomUUID
      ? `code_${self.crypto.randomUUID().replaceAll('-', '').slice(0, 16)}`
      : `code_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
    codebook.push({
      id,
      label: `新しいコード ${codebook.length + 1}`,
      description: '', include_example: '', exclude_example: '', category: '', theme: '',
      color: speakerThemeColors[codebook.length % speakerThemeColors.length]
    });
    analysisState.config.codebook = codebook;
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
    const target = analysisCard.querySelector(`[data-analysis-code-id="${id}"][data-analysis-code-field="label"]`);
    if (target) {
      target.focus();
      target.select();
    }
    return;
  }
  const removeCode = event.target.closest('[data-analysis-remove-code]');
  if (removeCode) {
    const codeId = removeCode.dataset.analysisRemoveCode;
    const code = (analysisState.config.codebook || []).find(item => item.id === codeId);
    const applied = Object.values(analysisState.annotations).some(item => (item.codes || []).includes(codeId));
    if (applied && !window.confirm(`「${code ? code.label : 'このコード'}」と発話への付与を削除しますか？`)) return;
    analysisState.config.codebook = (analysisState.config.codebook || []).filter(item => item.id !== codeId);
    Object.values(analysisState.annotations).forEach(item => {
      item.codes = (item.codes || []).filter(value => value !== codeId);
    });
    setAnalysisDirty(true);
    renderAnalysisWorkspace();
  }
});

listen(analysisCard, 'input', event => {
  const control = event.target;
  if (updateAnalysisConfigFromControl(control)) return;
  if (updateAnalysisCodeFromControl(control)) return;
  if (updateAnalysisAnnotationFromControl(control)) return;
  if (control.dataset.analysisSegmentQuery !== undefined) {
    analysisState.segmentQuery = control.value;
    syncAnalysisControls(control, '[data-analysis-segment-query]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  if (control.dataset.analysisAnnotatedOnly !== undefined) {
    analysisState.annotatedOnly = control.checked;
    syncAnalysisControls(control, '[data-analysis-annotated-only]', () => true);
    refreshAnalysisSegmentLists();
    return;
  }
  const speaker = control.dataset.analysisExcludedSpeaker;
  if (speaker !== undefined) {
    const excluded = new Set(analysisState.config.excluded_speakers || []);
    if (control.checked) excluded.add(speaker); else excluded.delete(speaker);
    analysisState.config.excluded_speakers = [...excluded];
    syncAnalysisControls(control, '[data-analysis-excluded-speaker]', peer => peer.dataset.analysisExcludedSpeaker === speaker);
    setAnalysisDirty(true);
  }
});

window.addEventListener('scroll', scheduleAnalysisNavigationSync, {passive: true});
window.addEventListener('resize', scheduleAnalysisNavigationSync, {passive: true});

const requestedParameters = new URLSearchParams(window.location.search);
const requestedSectionValue = requestedParameters.get('section');
const requestedAnalysisSection = ['overview', 'content', 'conversation', 'language', 'statistics', 'exports'].includes(requestedSectionValue)
  ? requestedSectionValue : '';

// `?view=` and `?item=` links (Vault links, older bookmarks) still work: they
// resolve to the matching hash route on first load.
function applyRouteFromLocation({fromHistory = false, initial = false} = {}) {
  let route = parseRouteHash(window.location.hash);
  if (!route && initial) {
    const requestedView = requestedParameters.get('view');
    const view = ['new', 'library', 'speakers', 'analysis'].includes(requestedView) ? requestedView : 'new';
    route = {view, itemId: view === 'analysis' ? String(requestedParameters.get('item') || '') : ''};
  }
  if (!route) route = {view: 'new', itemId: ''};
  if (route.view === 'item') {
    if (currentJob && String(currentJob.id) === route.itemId) {
      if (!showView('item', {itemId: route.itemId, replace: initial}) && fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    if (!confirmLeave({target: 'item', itemId: route.itemId})) {
      if (fromHistory) syncRouteHash(currentRouteHash);
      return;
    }
    const opening = openLibraryItem(route.itemId);
    const requestSequence = resultRequestSequence;
    opening.then(() => {
      // A stale route must not hide newer content or cancel its in-flight request.
      if (requestSequence !== resultRequestSequence) return;
      if (!currentJob || String(currentJob.id) !== route.itemId) showView('library', {replace: true});
    });
    return;
  }
  const opened = showView(route.view, {analysisItemId: route.view === 'analysis' ? route.itemId : '', replace: initial});
  if (!opened && fromHistory) syncRouteHash(currentRouteHash);
}

window.addEventListener('popstate', () => applyRouteFromLocation({fromHistory: true}));
applyRouteFromLocation({initial: true});
