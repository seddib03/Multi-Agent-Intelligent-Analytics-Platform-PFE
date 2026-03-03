export type Sector = "finance" | "transport" | "retail" | "manufacturing" | "public";
export type ProjectStatus = "preparation" | "ready" | "analysis" | "archived";
export type AnalysisType = "classification" | "regression" | "clustering" | "timeseries";
export type Severity = "critical" | "warning" | "info";
export type DataPrepStep = "upload" | "preview" | "metadata" | "quality" | "corrections" | "validation";
export type ChartStyle = "bar" | "line" | "pie" | "area" | "heatmap";
export type Density = "simplified" | "standard" | "expert";
export type AccentTheme = "royal-melon" | "blue-gold" | "midnight-peach" | "melon-royal" | "gold-blue" | "sky-midnight";

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  company: string;
}

export interface ColumnMetadata {
  originalName: string;
  businessName: string;
  type: "target" | "date" | "numeric" | "category" | "identifier" | "feature" | "ignore";
  unit: string;
  description: string;
  stats: {
    missing: number;
    missingPct: number;
    unique: number;
    min?: number;
    max?: number;
    mean?: number;
    median?: number;
    std?: number;
    topValues?: string[];
    dateRange?: [string, string];
  };
}

export interface QualityIssue {
  id: string;
  type: "missing" | "duplicates" | "outliers" | "type_mismatch" | "imbalance" | "correlation" | "invalid_dates";
  severity: Severity;
  title: string;
  description: string;
  affectedColumns: string[];
  affectedRows: number;
  correctionApplied?: string;
}

export interface Correction {
  issueId: string;
  method: string;
  impact: string;
}

export interface Project {
  id: string;
  title: string;
  useCaseDescription: string;
  analysisType: AnalysisType;
  timeHorizon: string;
  sector: Sector;
  status: ProjectStatus;
  createdAt: string;
  rowCount: number;
  columnCount: number;
  algorithm: string;
  fileName: string;
  qualityScore: number;
  pipelineProgress: number; // 0-100
}

export interface ModelResults {
  algorithm: string;
  auc: number;
  accuracy: number;
  f1Score: number;
  featureImportance: { feature: string; importance: number }[];
  topRiskyEntities: { id: string; name: string; risk: number; factors: string[] }[];
}

export interface Message {
  id: string;
  role: "user" | "system";
  content: string;
  timestamp: string;
  insights?: {
    chartType: ChartStyle;
    data: Record<string, unknown>[];
    title: string;
  };
  predictions?: Record<string, unknown>[];
  pinned?: boolean;
}

export interface UserPreferences {
  darkMode: boolean;
  chartStyle: ChartStyle;
  density: Density;
  accentTheme: AccentTheme;
  dashboardLayout: "grid" | "list";
  visibleKPIs: string[];
  primaryColor: string;
  secondaryColor: string;
}
