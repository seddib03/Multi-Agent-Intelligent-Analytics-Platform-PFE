export interface ColumnMetadata {
  originalName: string;
  businessName: string;
  semanticType: "target" | "date" | "numeric" | "category" | "identifier" | "ignore";
  unit: string;
  missingPercent: number;
}

export interface Entity {
  id: string;
  name: string;
  riskScore: number;
  mainFactor: string;
  trend: "up" | "down" | "stable";
}

export interface Message {
  id: string;
  role: "user" | "system";
  content: string;
  charts?: ChartData[];
  predictions?: Entity[];
  timestamp: Date;
  pinned?: boolean;
}

export interface ChartData {
  type: "bar" | "line" | "pie" | "area";
  title: string;
  data: Record<string, unknown>[];
  dataKeys: string[];
}

export type Sector = "finance" | "transport" | "retail" | "manufacturing" | "public";
export type ChartStyle = "bar" | "line" | "pie" | "area" | "heatmap";
export type Density = "simplified" | "standard" | "expert";
export type AccentTheme = "royal-melon" | "blue-gold" | "midnight-peach" | "melon-royal" | "gold-blue" | "sky-midnight";

export const ACCENT_THEMES: Record<AccentTheme, { primary: string; secondary: string; label: string }> = {
  "royal-melon": { primary: "#004AAC", secondary: "#FF7E51", label: "Royal & Melon" },
  "blue-gold": { primary: "#4995FF", secondary: "#FFAE41", label: "Blue & Gold" },
  "midnight-peach": { primary: "#0E1020", secondary: "#FFC982", label: "Midnight & Peach" },
  "melon-royal": { primary: "#FF7E51", secondary: "#004AAC", label: "Melon & Royal" },
  "gold-blue": { primary: "#FFAE41", secondary: "#4995FF", label: "Gold & Blue" },
  "sky-midnight": { primary: "#A1E6FF", secondary: "#0E1020", label: "Sky & Midnight" },
};

export const DXC_CHART_COLORS = ["#004AAC", "#FF7E51", "#FFAE41", "#4995FF", "#FFC982", "#A1E6FF"];

export type Language = "fr" | "en";

export interface SavedProject {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  currentPhase: 1 | 2 | 3;
  onboardingStep: 1 | 2 | 3 | 4 | 5;
  onboarding: AppState["onboarding"];
  dataset: AppState["dataset"];
  modelResults: AppState["modelResults"];
  messages: Message[];
  pinnedInsights: Message[];
}

export interface AppState {
  currentPhase: 1 | 2 | 3;
  onboardingStep: 1 | 2 | 3 | 4 | 5;
  currentConversationId: string | null;
  currentProjectId: string | null;
  savedProjects: SavedProject[];
  onboarding: {
    useCaseDescription: string;
    analysisTypes: string[];
    timeHorizon: string;
  };
  dataset: {
    fileName: string;
    rowCount: number;
    columnCount: number;
    columns: ColumnMetadata[];
    qualityScore: number;
    businessRules: string;
    detectedSector: Sector;
    previewData: Record<string, unknown>[];
  };
  modelResults: {
    algorithm: string;
    auc: number;
    accuracy: number;
    f1Score: number;
    precision: number;
    recall: number;
    rmse: number;
    gini: number;
    logLoss: number;
    featureImportance: { feature: string; importance: number }[];
    topRiskyEntities: Entity[];
  };
  messages: Message[];
  pinnedInsights: Message[];
  userPreferences: {
    darkMode: boolean;
    chartStyle: ChartStyle;
    density: Density;
    accentTheme: AccentTheme;
    dashboardLayout: "grid" | "list";
    visibleKPIs: string[];
    primaryColor: string;
    secondaryColor: string;
    language: Language;
  };
  // Actions
  setPhase: (phase: 1 | 2 | 3) => void;
  setOnboardingStep: (step: 1 | 2 | 3 | 4 | 5) => void;
  updateOnboarding: (data: Partial<AppState["onboarding"]>) => void;
  updateDataset: (data: Partial<AppState["dataset"]>) => void;
  updatePreferences: (prefs: Partial<AppState["userPreferences"]>) => void;
  addMessage: (msg: Message) => void;
  togglePin: (msgId: string) => void;
  updateModelResults: (results: Partial<AppState["modelResults"]>) => void;
  clearMessages: () => void;
  saveCurrentProject: () => void;
  loadProject: (projectId: string) => void;
  deleteProject: (projectId: string) => void;
  resetProject: () => void;
}
