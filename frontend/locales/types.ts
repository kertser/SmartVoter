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
}

