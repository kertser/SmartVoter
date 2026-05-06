/** Shared type for all locale translation objects. */

export interface EvidenceRow {
  type: string;
  weight: string;
  description: string;
}

export interface Translations {
  lang: "en" | "he" | "ru";
  dir: "ltr" | "rtl";

  layout: {
    siteTitle: string;
    navMethodology: string;
    navSimulation: string;
    navParties: string;
    navVotes: string;
    navBills: string;
    navPersons: string;
    navAdmin: string;
    navPartiesTitle: string;
    navVotesTitle: string;
    navBillsTitle: string;
    navPersonsTitle: string;
    navAdminTitle: string;
    navSimulationTitle: string;
    navMethodologyTitle: string;
    footerDisclaimer: string;
  };

  langSwitcher: {
    label: string;
    en: string;
    he: string;
    ru: string;
    enTooltip: string;
    heTooltip: string;
    ruTooltip: string;
  };

  home: {
    badge: string;
    headline1: string;
    headline2: string;
    headlineEmphasis: string;
    headlineEnd: string;
    subtext: string;
    subtextStrong: string;
    subtextEnd: string;
    beforeYouBegin: string;
    disclaimer: [string, string, string, string];
    ctaStart: string;
    ctaMethodology: string;
    trust1: string;
    trust2: string;
    trust3: string;
    trust4: string;
    trust1Tooltip: string;
    trust2Tooltip: string;
    trust3Tooltip: string;
    trust4Tooltip: string;
  };

  questionnaire: {
    progressLabel: (current: number, max: number) => string;
    showResultsNow: string;
    positionLabel: string;
    positionTooltip: string;
    importanceLabel: string;
    importanceTooltip: string;
    whyAsked: string;
    whyAskedHide: string;
    whyAskedShow: string;
    submitNext: string;
    submitting: string;
    loadingQuestion: string;
    errorLoad: string;
    errorSubmit: string;
    tryAgain: string;
    likert: {
      stronglyOppose: string;
      somewhatOppose: string;
      neutral: string;
      somewhatSupport: string;
      stronglySupport: string;
    };
    salience: {
      notImportant: string;
      important: string;
      veryImportant: string;
    };
  };

  results: {
    basedOnEvidence: string;
    heading: string;
    description: string;
    howCalculated: string;
    loadingResults: string;
    errorLoad: string;
    backToStart: string;
    partyMatchesHeading: string;
    representationHeading: string;
    bestPartyByTopic: string;
    viewMethodology: string;
    startOver: string;
    matchLabel: string;
    confidenceLabel: (level: string) => string;
    evidenceLabel: (pct: string) => string;
    coverageLabel: (pct: string) => string;
    newParty: string;
    highVolatility: string;
    showDetails: string;
    hideDetails: string;
    agreements: string;
    disagreements: string;
    noAgreements: string;
    noDisagreements: string;
    confidenceLow: string;
    confidenceMedium: string;
    confidenceHigh: string;
    // Sections
    topicComparisonHeading: string;
    evidenceQualityHeading: string;
    partyLineageHeading: string;
    noTopicData: string;
    evidenceDrawerTitle: string;
    evidenceDrawerClose: string;
    evidenceTypeLabel: string;
    positionLabel: string;
    uncertaintyLabel: string;
    sourceRefsLabel: string;
    noSources: string;
    humanReviewLabel: string;
    lineageRelationLabel: string;
    continuityWeightLabel: string;
    // Tooltips
    tooltipMatchScore: string;
    tooltipConfidence: string;
    tooltipEvidence: string;
    tooltipCoverage: string;
    tooltipVolatility: string;
    tooltipNewParty: string;
    tooltipScoreBar: string;
  };

  methodology: {
    backHome: string;
    heading: string;
    subtext: string;
    corePrincipleHeading: string;
    corePrinciple: string;
    matchScoreHeading: string;
    matchScoreDescription: string;
    notePositions: string;
    confidenceScoreHeading: string;
    confidenceScoreDescription: string;
    coverageLabel: string;
    coverageDescription: string;
    stabilityLabel: string;
    stabilityDescription: string;
    volatilityLabel: string;
    volatilityDescription: string;
    evidenceStrengthLabel: string;
    evidenceStrengthDescription: string;
    evidencePriorityHeading: string;
    evidencePriorityDescription: string;
    tableEvidenceType: string;
    tableWeight: string;
    tableNote: string;
    evidenceRows: EvidenceRow[];
    newPartyHeading: string;
    newPartyWarningTitle: string;
    newPartyWarningBody: string;
    limitationsHeading: string;
    limitations: [string, string, string, string, string];
  };

  browser: {
    evidenceBrowser: string;
    methodologyLink: string;
    loading: string;
    source: string;
    noItemsFound: string;

    // Parties page
    partiesHeading: string;
    partiesDesc: string;
    filterActive: string;
    filterAll: string;
    knessetLabel: (n: number) => string;
    electionCycleLabel: (cycle: string) => string;
    // Party status badge tooltips
    statusActiveTooltip: string;
    statusDissolvedTooltip: string;
    statusMergedTooltip: string;
    statusSplitTooltip: string;
    statusRenamedTooltip: string;
    // Party detail tooltips
    positionBarTooltip: string;
    evidenceStrengthTooltip: string;
    evidenceTypeTooltip: string;
    continuityWeightTooltip: string;

    // Votes page
    votesHeading: string;
    votesDesc: string;
    searchVotes: string;
    allKnessets: string;
    knessetN: (n: number) => string;
    importanceLabel: (pct: number) => string;

    // Bills page
    billsHeading: string;
    billsDesc: string;
    searchBills: string;

    // Persons page
    personsHeading: string;
    personsDesc: string;
    searchPersons: string;
    birthYear: (year: number) => string;
    countOf: (shown: number, total: number) => string;
  };

  admin: {
    passwordGateHeading: string;
    passwordGateSubtext: string;
    passwordLabel: string;
    passwordPlaceholder: string;
    passwordSubmit: string;
    passwordError: string;
    passwordLogout: string;
    heading: string;
    subtext: string;
    tabReview: string;
    tabGenerate: string;
    tabAudit: string;
    tabIngestion: string;
    reviewNoItems: string;
    reviewSelectFilter: string;
    reviewFilterAll: string;
    reviewFilterNeedsReview: string;
    reviewFilterDraft: string;
    reviewFilterLlmGenerated: string;
    reviewFilterRejected: string;
    reviewRefresh: string;
    reviewApprove: string;
    reviewApproveAll: string;
    reviewApproveAllConfirm: (n: number) => string;
    reviewApproveAllSuccess: (n: number) => string;
    reviewApproveAllError: string;
    reviewEdit: string;
    reviewReject: string;
    reviewSave: string;
    reviewCancel: string;
    reviewEnLabel: string;
    reviewHeLabel: string;
    reviewRuLabel: string;
    reviewNeutrality: string;
    reviewPrompt: string;
    generateHeading: string;
    generateSeedNote: string;
    generateRuntimeNote: string;
    generateSelectAll: string;
    generateClearAll: string;
    generateBtn: (n: number) => string;
    generateGenerating: string;
    generateSuccessMsg: (n: number) => string;
    auditHeading: string;
    auditNoData: string;
    auditColWhen: string;
    auditColProvider: string;
    auditColType: string;
    auditColConfidence: string;
    auditColSummary: string;
    onlyApprovedNote: string;
    // Ingestion tab
    ingestHeading: string;
    ingestSubtext: string;
    ingestKnessetLabel: string;
    ingestLimitLabel: string;
    ingestNoLlmLabel: string;
    ingestVotesOnlyLabel: string;
    ingestBillsOnlyLabel: string;
    ingestRunBtn: string;
    ingestRunning: string;
    ingestQueued: string;
    ingestDone: string;
    ingestError: string;
    ingestJobId: string;
    ingestPollBtn: string;
    ingestResultVotes: (inserted: number, updated: number, skipped: number) => string;
    ingestResultBills: (inserted: number, skipped: number) => string;
    ingestResultFactions: (inserted: number, updated: number) => string;
    ingestResultPersons: (inserted: number, skipped: number) => string;
    ingestResultVoteResults: (inserted: number, skipped: number) => string;
    ingestResultPolicyItems: (created: number, skipped: number) => string;
    ingestResultPartyPositions: (created: number, updated: number) => string;
    ingestResultQuestions: (created: number, skipped: number) => string;
    ingestResultLineage: (edges: number) => string;
    ingestResultVolatility: (candidates: number, parties: number) => string;
    ingestStepError: (step: string, msg: string) => string;
    ingestKnesset25Warning: string;
    // Full Pipeline Wizard
    pipelineWizardHeading: string;
    pipelineWizardSubtext: string;
    pipelineWizardLastNLabel: string;
    pipelineWizardNoLlmLabel: string;
    pipelineWizardNoLlmNote: string;
    pipelineWizardRunBtn: string;
    pipelineWizardKnessetsLabel: (knessets: number[]) => string;
    pipelineWizardPhase1: string;
    pipelineWizardPhase2: string;
    pipelineWizardCurrentStep: (step: string) => string;
    pipelineWizardDone: string;
    pipelineWizardError: string;
    pipelineWizardStatusPrefix: string;
    pipelineWizardKnessetPending: string;
    pipelineWizardKnessetRunning: (kn: number) => string;
    pipelineWizardKnessetDone: (kn: number) => string;
    pipelineWizardVotesSkipped: string;
    pipelineWizardCurrentKnessetLabel: string;
    pipelineWizardCurrentKnessetNote: (n: number) => string;
    pipelineWizardVotesApiNote: string;
    pipelineWizardLlmCostWarning: string;
    ingestManualTitle: string;
    ingestManualSubtext: string;
    ingestManualShowBtn: string;
    ingestManualHideBtn: string;
    // Question tree (Generate tab)
    generateTopicHeading: string;
    generateTopicSubtext: string;
    generateRootBtn: string;
    generateRootGenerating: string;
    generateRootUpdateBtn: string;
    generateRootExists: string;
    generateRootNone: string;
    generatePolicyItemCount: (n: number) => string;
    generateFollowupCount: (n: number) => string;
    generateRootStatus: (s: string) => string;
    // Generate All
    generateAllBtn: string;
    generateAllForceLabel: string;
    generateAllSkipLabel: string;
    generateAllWorkersLabel: string;
    generateAllRunning: (completed: number, total: number, current: string | null) => string;
    generateAllDone: (created: number, updated: number, skipped: number, errors: number) => string;
    generateAllError: string;
    // Manual question entry
    manualEntryHeading: string;
    manualEntrySubtext: string;
    manualEntryTopicLabel: string;
    manualEntryIsRoot: string;
    manualEntryEnLabel: string;
    manualEntryHeLabel: string;
    manualEntryRuLabel: string;
    manualEntryContextLabel: string;
    manualEntrySubmitBtn: string;
    manualEntrySubmitting: string;
    manualEntrySuccess: (action: string) => string;
    manualEntryEnPlaceholder: string;
    manualEntryHePlaceholder: string;
    manualEntryRuPlaceholder: string;
    // Backup / Restore tab
    tabBackup: string;
    backupHeading: string;
    backupSubtext: string;
    backupDownloadBtn: string;
    backupDownloading: string;
    backupRestoreHeading: string;
    backupRestoreSubtext: string;
    backupRestoreBtn: string;
    backupRestoring: string;
    backupSkipExistingLabel: string;
    backupRestoreSuccess: (inserted: number, skipped: number) => string;
    backupRestoreError: string;
  };

  privacy: {
    bannerText: string;
    learnMore: string;
    accept: string;
    policyHeading: string;
    policyBody: string;
    deleteSessionBtn: string;
    deleteSessionConfirm: string;
    deleteSessionSuccess: string;
    deleteSessionError: string;
  };

  simulation: {
    heading: string;
    subheading: string;
    disclaimer: string;
    loadingSimulation: string;
    errorLoad: string;
    runNewSimulation: string;
    running: string;
    semicircleHeading: string;
    semicircleDesc: string;
    seatDistributionHeading: string;
    seatDistributionDesc: string;
    thresholdRiskHeading: string;
    thresholdRiskDesc: string;
    coalitionScenariosHeading: string;
    coalitionScenariosDesc: string;
    assumptionsHeading: string;
    assumptionsShow: string;
    assumptionsHide: string;
    seatsLabel: string;
    seatsMedianLabel: string;
    intervalLabel: string;
    thresholdProbLabel: string;
    feasibilityLabel: string;
    stabilityLabel: string;
    probabilityLabel: string;
    membersLabel: string;
    noScenarios: string;
    dataCutoff: (date: string) => string;
    modelVersionLabel: string;
    iterationsLabel: string;
    totalSeatsLabel: string;
    dataNote: string;
    notPrediction: string;
    coalSeats: (mean: number, p10: number, p90: number) => string;
    coalFeasibility: (score: number) => string;
    coalStability: (score: number) => string;
    // Tooltips
    feasibilityTooltip: string;
    stabilityTooltip: string;
    coalProbabilityTooltip: string;
    thresholdProbTooltip: string;
    runNewSimulationTooltip: string;
  };
}

