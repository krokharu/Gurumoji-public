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
const haasBackendNote = document.querySelector('#haas-backend-note');
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
const priorDataPanels = [...document.querySelectorAll('[data-prior-panel]')];
const priorDataButtons = [...document.querySelectorAll('[data-prior-view]')];
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

const reducedMotionMedia = window.matchMedia('(prefers-reduced-motion: reduce)');

// One stepper for every width (UX-05): on a desktop it reports progress and
// scrolls to the section; on a phone it is the wizard's page indicator.

// Detailed settings stay closed until asked for; "変更" opens exactly one panel.

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

// Advisory notes (not blockers) are shown until a job that displayed them has
// been accepted, so each one appears only the first time its feature is used.
const seenNoticeStorageKey = 'gurumoji.seenCreateNotices';

// ---- Screens and routes (UX-01). Each screen owns one hash so reloads, the
// browser's back button and bookmarks return to the same place. ----
const viewRouteHashes = {new: '#/new', library: '#/data', analysis: '#/analysis', speakers: '#/speakers',
  presets: '#/presets', folders: '#/folders', catalog: '#/catalog', internal: '#/internal'};

// 分析は公開準備中のため、実行データを読み込まない。
const ANALYSIS_COMING_SOON = document.documentElement.dataset.analysisEnabled !== 'true';
if (analysisCard) analysisCard.classList.toggle('is-coming-soon', ANALYSIS_COMING_SOON);

// Every move between screens passes these checks, so unsaved edits are never
// dropped without asking (UX-30).

// Tabs inside one record's workspace (UX-02): editing, conversation, summary, files.

// The header chip is the only job indicator outside the create screen (UX-16).

listen(showLibraryButton, 'click', () => showView('library'));
listen(showAnalysisButton, 'click', () => showView('analysis'));
listen(showLibraryListButton, 'click', () => showView('library'));
listen(showLibraryAnalysisButton, 'click', () => showView('analysis'));
listen(showNewButton, 'click', () => showView('new'));
listen(showSpeakersButton, 'click', () => showView('speakers'));
priorDataButtons.forEach(button => listen(button, 'click', () => showView(button.dataset.priorView)));
// タブの矢印キー移動はフォーカスだけを変え、Enter・Spaceで画面を選ぶ。
listen(document.querySelector('.app-nav'), 'keydown', event => {
  const tabs = [...event.currentTarget.querySelectorAll('[role="tab"]')];
  const index = tabs.indexOf(event.target);
  if (index < 0) return;
  let next;
  if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
  else if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
  else if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = tabs.length - 1;
  else return;
  event.preventDefault();
  tabs[next].focus();
  tabs[next].scrollIntoView({block: 'nearest', inline: 'nearest'});
});
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

listen(document.querySelector('#export-result-draft'), 'click', () => downloadUnsavedDraft('transcript'));
listen(document.querySelector('#export-speaker-draft'), 'click', () => downloadUnsavedDraft('speakers'));

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
  const dropped = [...((event.dataTransfer && event.dataTransfer.files) || [])];
  const file = dropped[0];
  if (!file) return;
  // The create dashboard keeps a list of registered files; without it only the first one is used.
  if (typeof window.registerSourceFiles === 'function') {
    window.registerSourceFiles(dropped, {append: true});
    return;
  }
  try {
    const transfer = new DataTransfer();
    transfer.items.add(file);
    inputFile.files = transfer.files;
    handleInputFileSelection();
  } catch (error) {
    setAlert(pathError, 'ドラッグ＆ドロップを利用できません。［ファイルを選択］から指定してください。', true);
  }
});

['model-name', 'transcription-device', 'diarization-device'].forEach(id => {
  listen(document.getElementById(id), 'change', () => manuallySelectedMachineFields.add(id));
});
listen(document.querySelector('#machine-reset-button'), 'click', () => applyMachineProfile(lastMachineProfile, {reset: true}));
listen(document.querySelector('#setup-open-connections'), 'click', () => document.querySelector('#connection-button')?.click());
listen(document.querySelector('#setup-recheck'), 'click', loadConfig);
listen(document.querySelector('#model-readiness-ack'), 'change', updateCreateSummary);

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

// Remember optional choices per finishing mode. A mode's mandated execution
// is modeled separately by aiEffortStagePlan, not by rewriting another mode's
// preferences. This is transient form state, never a second effort store.
const transcriptFinishingPreferences = new Map();
let lastTranscriptFinishingMode = selectedTranscriptFinishingMode();

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
// Create-screen sidebar: the rest of the shortcuts and the open-panel highlight.
document.querySelectorAll('[data-open-source-settings]').forEach(button => {
  listen(button, 'click', () => {
    const details = document.querySelector('#setup-source .source-advanced');
    if (!details) return;
    details.open = true;
    details.scrollIntoView({behavior: scrollBehavior(), block: 'center'});
  });
});
document.querySelectorAll('[data-open-connection]').forEach(button => {
  listen(button, 'click', () => document.querySelector('#connection-button')?.click());
});
const sidebarPanelButtons = [...document.querySelectorAll('.create-sidebar [data-open-panel]')];

settingsPanels.forEach(panel => listen(panel, 'toggle', syncSidebarPanels));
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
    rememberSeenNotices(readiness.notes);
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

// DATA-01: deleted conversations wait in the trash until restored, purged or expired.

['#library-speaker', '#library-emotion', '#library-group', '#library-sort', '#library-recorded-from', '#library-recorded-to', '#library-media-duration-min', '#library-media-duration-max'].forEach(selector => {
  listen(document.querySelector(selector), 'change', () => loadLibrary());
});
listen(document.querySelector('#library-keyword'), 'input', () => {
  window.clearTimeout(libraryTimer);
  libraryTimer = window.setTimeout(loadLibrary, 250);
});

listen(document.querySelector('#library-clear-filters'), 'click', clearLibraryFilters);
listen(document.querySelector('#library-filter-toggle'), 'click', event => {
  setLibraryFiltersOpen(event.currentTarget.getAttribute('aria-expanded') !== 'true');
});
listen(document.querySelector('#library-refresh-button'), 'click', () => {
  trainingStatusLoaded = false;
  loadLibrary();
});
listen(document.querySelector('#library-create-new-button'), 'click', () => showView('new'));

listen(document.querySelector('#manage-library-groups-button'), 'click', () => showView('folders'));
listen(document.querySelector('#close-library-group-dialog'), 'click', () => showView('library'));
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

// Speech is the union of the timed segments inside [from, to], so overlapping
// speakers are not counted twice; silence is whatever is left of the range.

let activePlaybackSegmentId = null;

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

listen(document.querySelector('#undo-segment-delete'), 'click', undoSegmentDeletion);

listen(rerunSpeakerIdentificationButton, 'click', rerunSpeakerIdentification);

// Rebuilds the AI outline (and its overall summary) from the saved transcript.
// Only the outline is replaced; the transcript and speaker names are not touched.
const outlineRerunButton = document.querySelector('#outline-rerun-button');
const outlineRerunProvider = document.querySelector('#outline-rerun-provider');
const outlineRerunStatus = document.querySelector('#outline-rerun-status');

listen(outlineRerunButton, 'click', rerunOutline);

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

// Shared analysis charts and navigation are in analysis-visualizations.js.

// Method-specific analysis rendering is in analysis-method-view.js.

let preparationDraft = null;
let preparationDirty = false;
let preparationSaving = false;

const requestedParameters = new URLSearchParams(window.location.search);
const requestedSectionValue = requestedParameters.get('section');
const requestedAnalysisSection = ['overview', 'content', 'conversation', 'language', 'statistics', 'exports'].includes(requestedSectionValue)
  ? requestedSectionValue : '';

// `?view=` and `?item=` links (Vault links, older bookmarks) still work: they
// resolve to the matching hash route on first load.

window.addEventListener('popstate', () => applyRouteFromLocation({fromHistory: true}));
applyRouteFromLocation({initial: true});
