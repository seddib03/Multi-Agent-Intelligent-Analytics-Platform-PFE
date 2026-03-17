import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, ChevronDown, ChevronLeft, ChevronRight, FileUp, Info, Maximize2, Minimize2, RotateCcw, X } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { SECTOR_LABELS } from "@/lib/mockData";
import type { ColumnMetadata, Sector } from "@/types/app";
import { t } from "@/lib/i18n";
import { toast } from "sonner";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { uploadDatasetDictionary, updateDatasetMetadata, type DatasetMetadataColumnUpdate } from "@/lib/datasetsApi";
import { updateProject } from "@/lib/projectsApi";

type SemanticType = "numeric" | "date" | "category" | "target" | "identifier" | "ignore";

const TYPE_BADGES: Record<SemanticType, { className: string; icon: string; label: string }> = {
  numeric:    { className: "bg-dxc-royal text-white", icon: "🔢", label: "Numérique" },
  category:   { className: "bg-dxc-gold text-dxc-midnight", icon: "🔤", label: "Texte" },
  date:       { className: "bg-dxc-sky text-dxc-midnight", icon: "📅", label: "Date / Heure" },
  target:     { className: "bg-dxc-melon text-white", icon: "🎯", label: "Cible" },
  identifier: { className: "bg-neutral-500 text-white", icon: "🆔", label: "Identifiant" },
  ignore:     { className: "bg-orange-700 text-white", icon: "🚫", label: "Ignorer" },
};

type DictionaryEntry = {
  originalName: string;
  businessName?: string;
  semanticType?: SemanticType;
  description?: string;
  extras?: Record<string, string>;
};

type UploadedDataset = { fileName: string; columns: ColumnMetadata[]; datasetId?: string };

type DatasetDictionaryStatus = {
  fileName: string | null;
  summary: { matched: number; remaining: number } | null;
  error: string | null;
  undoSnapshot: UploadedDataset[] | null;
  storedDictionaryPath: string | null;
  storedDictionaryName: string | null;
  storedDictionaryEntries: DictionaryEntry[] | null;
};

const FIELD_ALIASES = {
  originalName: [
    "originalname",
    "original_name",
    "nomoriginal",
    "nomtechnique",
    "technicalname",
    "column",
    "columnname",
    "colonne",
    "field",
    "name",
    "sourcefield",
    "sourcecolumn",
    "variablename",
  ],
  businessName: [
    "businessname",
    "business_name",
    "nommetier",
    "displayname",
    "friendlyname",
    "label",
    "title",
    "metier",
  ],
  semanticType: [
    "semantictype",
    "semantic_type",
    "type",
    "businesstype",
    "business_type",
    "datatype",
    "role",
    "usage",
  ],
  description: [
    "description",
    "definition",
    "desc",
    "details",
    "meaning",
    "comment",
    "commentaire",
  ],
} as const;

const SEMANTIC_TYPE_ALIASES: Record<SemanticType, string[]> = {
  numeric: ["numeric", "number", "decimal", "float", "double", "integer", "int", "mesure", "quantitative", "numerique"],
  date: ["date", "datetime", "timestamp", "time", "temporal", "calendaire"],
  category: ["category", "categorical", "text", "string", "boolean", "bool", "texte", "nominal"],
  target: ["target", "label", "outcome", "prediction", "class", "cible", "y"],
  identifier: ["identifier", "id", "key", "primarykey", "identifiant", "cle"],
  ignore: ["ignore", "ignored", "drop", "exclude", "excluded", "skip", "ignorer"],
};

const BASE_METADATA_KEYS = new Set([
  "originalName",
  "businessName",
  "semanticType",
  "description",
  "missingPercent",
]);

const TECHNICAL_METADATA_KEYS = new Set([
  "detectedType",
  "uniqueCount",
  "sampleValues",
  "unit",
]);

const EXTRA_KEY_ORDER = ["pattern", "nullable", "min", "max", "dateFormat", "enums"];
const SUPPORTED_SECTORS = Object.keys(SECTOR_LABELS) as Sector[];

function normalizeSector(value: string | null | undefined): Sector | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  return SUPPORTED_SECTORS.includes(normalized as Sector) ? (normalized as Sector) : null;
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toStringValue(value: unknown): string | undefined {
  if (value == null) return undefined;
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : undefined;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    const normalized = value
      .map((item) => (typeof item === "string" || typeof item === "number" || typeof item === "boolean" ? String(item) : JSON.stringify(item)))
      .join(", ")
      .trim();
    return normalized || undefined;
  }
  if (typeof value === "object") {
    const serialized = JSON.stringify(value);
    return serialized && serialized !== "{}" ? serialized : undefined;
  }
  return undefined;
}

function canonicalizeExtraKey(rawKey: string): string {
  const compact = normalizeText(rawKey);

  if (["pattern", "regex", "regexp"].includes(compact)) return "pattern";
  if (["nullable", "isnullable", "allownull", "nullability", "null"].includes(compact)) return "nullable";
  if (["min", "minimum"].includes(compact)) return "min";
  if (["max", "maximum"].includes(compact)) return "max";
  if (["range", "minmax", "interval", "bounds", "limits"].includes(compact)) return "";
  if (["dateformat", "datetimeformat", "formatdate", "format"].includes(compact)) return "dateFormat";
  if (["enum", "enums", "allowedvalues", "categories", "values"].includes(compact)) return "enums";

  return rawKey.trim();
}

function isExtraMetadataKey(key: string): boolean {
  return !BASE_METADATA_KEYS.has(key) && !TECHNICAL_METADATA_KEYS.has(key);
}

function formatExtraMetadataKeyLabel(key: string): string {
  if (key === "dateFormat") return "Date format";
  if (key === "pattern") return "Pattern";
  if (key === "nullable") return "Nullable";
  if (key === "min") return "Min";
  if (key === "max") return "Max";
  if (key === "enums") return "Enums";
  return key;
}

function getExtraColumnWidthClass(key: string, fullscreen: boolean): string {
  if (!fullscreen) return "";
  if (["pattern", "nullable", "min", "max"].includes(key)) return "min-w-[130px]";
  if (key === "dateFormat") return "min-w-[180px]";
  if (key === "enums") return "min-w-[200px]";
  return "min-w-[180px]";
}

function shouldShowExtraFieldForType(key: string, semanticType: SemanticType): boolean {
  const normalizedKey = normalizeText(key);

  if (["pattern", "nullable", "isnullable", "allownull", "nullability", "null"].includes(normalizedKey)) {
    return true;
  }

  if (["min", "minimum", "max", "maximum"].includes(normalizedKey)) {
    return semanticType === "numeric";
  }

  if (["enum", "enums", "allowedvalues", "categories", "category", "values"].includes(normalizedKey)) {
    return semanticType === "category";
  }

  if (["dateformat", "datetimeformat", "formatdate", "format"].includes(normalizedKey)) {
    return semanticType === "date";
  }

  return true;
}

function readField(row: Record<string, unknown>, aliases: readonly string[]): string | undefined {
  const aliasSet = new Set(aliases.map(normalizeText));
  for (const [key, value] of Object.entries(row)) {
    if (aliasSet.has(normalizeText(key))) {
      return toStringValue(value);
    }
  }
  return undefined;
}

function mapSemanticType(value: unknown): SemanticType | undefined {
  const normalized = toStringValue(value);
  if (!normalized) return undefined;
  const compact = normalizeText(normalized);

  for (const [semanticType, aliases] of Object.entries(SEMANTIC_TYPE_ALIASES) as [SemanticType, string[]][]) {
    if (aliases.some((alias) => normalizeText(alias) === compact)) {
      return semanticType;
    }
  }

  return undefined;
}

function parseDelimitedLine(line: string, delimiter: string): string[] {
  const cells: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const nextChar = line[index + 1];

    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        current += '"';
        index += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (char === delimiter && !inQuotes) {
      cells.push(current.trim());
      current = "";
      continue;
    }

    current += char;
  }

  cells.push(current.trim());
  return cells;
}

function detectDelimiter(headerLine: string): string {
  const candidates = [",", ";", "\t", "|"];
  return candidates.reduce((best, candidate) => {
    const score = headerLine.split(candidate).length;
    const bestScore = headerLine.split(best).length;
    return score > bestScore ? candidate : best;
  }, ",");
}

function parseDelimitedDictionary(text: string): Record<string, unknown>[] {
  const lines = text
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  if (lines.length < 2) return [];

  const delimiter = detectDelimiter(lines[0]);
  const headers = parseDelimitedLine(lines[0], delimiter);

  return lines.slice(1).map((line) => {
    const values = parseDelimitedLine(line, delimiter);
    return headers.reduce<Record<string, unknown>>((acc, header, index) => {
      acc[header] = values[index] ?? "";
      return acc;
    }, {});
  });
}

function parseJsonDictionary(content: unknown): Record<string, unknown>[] {
  if (Array.isArray(content)) {
    return content.filter(isRecord);
  }

  if (!isRecord(content)) {
    return [];
  }

  const nestedCollection = content.columns ?? content.dictionary ?? content.data_dictionary ?? content.dataDictionary ?? content.entries;
  if (Array.isArray(nestedCollection)) {
    return nestedCollection.filter(isRecord);
  }

  if (isRecord(nestedCollection)) {
    return Object.entries(nestedCollection).map(([originalName, value]) => ({
      originalName,
      ...(isRecord(value) ? value : { description: value }),
    }));
  }

  const values = Object.values(content);
  if (values.length > 0 && values.every(isRecord)) {
    return Object.entries(content).map(([originalName, value]) => ({
      originalName,
      ...(isRecord(value) ? value : {}),
    }));
  }

  return [];
}

function toDictionaryEntry(row: Record<string, unknown>): DictionaryEntry | null {
  const originalName = readField(row, FIELD_ALIASES.originalName);
  if (!originalName) return null;

  const knownAliases = new Set(
    [...FIELD_ALIASES.originalName, ...FIELD_ALIASES.businessName, ...FIELD_ALIASES.semanticType, ...FIELD_ALIASES.description]
      .map(normalizeText),
  );

  const extras: Record<string, string> = {};
  for (const [key, value] of Object.entries(row)) {
    if (knownAliases.has(normalizeText(key))) continue;

    const textValue = toStringValue(value);
    if (!textValue) continue;

    const canonicalKey = canonicalizeExtraKey(key);
    if (!canonicalKey || !isExtraMetadataKey(canonicalKey)) continue;
    extras[canonicalKey] = textValue;
  }

  return {
    originalName,
    businessName: readField(row, FIELD_ALIASES.businessName),
    semanticType: mapSemanticType(readField(row, FIELD_ALIASES.semanticType)),
    description: readField(row, FIELD_ALIASES.description),
    extras,
  };
}

function isColumnComplete(column: ColumnMetadata): boolean {
  return Boolean(
    column.businessName.trim() &&
    column.semanticType &&
    (column.description ?? "").trim(),
  );
}

function isUnnamedColumn(originalName: string): boolean {
  const normalized = originalName.trim().toLowerCase();
  return normalized === "unnamed" || /^unnamed\s*:\s*\d+$/i.test(normalized);
}

function cloneUploadedDatasets(datasets: UploadedDataset[]): UploadedDataset[] {
  return datasets.map((dataset) => ({
    fileName: dataset.fileName,
    datasetId: dataset.datasetId,
    columns: dataset.columns.map((column) => ({ ...column })),
  }));
}

function createEmptyDatasetDictionaryStatus(): DatasetDictionaryStatus {
  return {
    fileName: null,
    summary: null,
    error: null,
    undoSnapshot: null,
    storedDictionaryPath: null,
    storedDictionaryName: null,
    storedDictionaryEntries: null,
  };
}

function syncDatasetStatuses(
  statuses: DatasetDictionaryStatus[],
  datasetCount: number,
): DatasetDictionaryStatus[] {
  return Array.from({ length: datasetCount }, (_, index) => statuses[index] ?? createEmptyDatasetDictionaryStatus());
}

function getVisibleDatasetColumns(columns: ColumnMetadata[]): Array<{ col: ColumnMetadata; index: number }> {
  return columns
    .map((col, index) => ({ col, index }))
    .filter(({ col }) => !isUnnamedColumn(col.originalName));
}

function getIncompleteDatasetRows(columns: ColumnMetadata[]) {
  return getVisibleDatasetColumns(columns)
    .map(({ col, index }) => ({
      index,
      originalName: col.originalName,
      missingBusinessName: !col.businessName.trim(),
      missingDescription: !(col.description ?? "").trim(),
      missingSemanticType: !col.semanticType,
    }))
    .filter((row) => row.missingBusinessName || row.missingDescription || row.missingSemanticType);
}

export function StepMetadata() {
  const { dataset, onboarding, updateDataset, setOnboardingStep, userPreferences, currentProjectId } = useAppStore();
  const lang = userPreferences.language;
  const { detectedSector, businessRules } = dataset;
  const sectorContext = onboarding.sectorContext;

  const uploadedDatasets = useMemo<UploadedDataset[]>(
    () => (
      (dataset as never as { uploadedDatasets?: UploadedDataset[] })
        .uploadedDatasets ?? [{ fileName: dataset.fileName, columns: dataset.columns, datasetId: undefined }]
    ),
    [dataset],
  );

  const [activeDsIdx, setActiveDsIdx] = useState(0);
  const [localDatasets, setLocalDatasets] = useState(uploadedDatasets);
  const [datasetStatuses, setDatasetStatuses] = useState<DatasetDictionaryStatus[]>(() =>
    uploadedDatasets.map(() => createEmptyDatasetDictionaryStatus()),
  );
  const [attemptedNext, setAttemptedNext] = useState(false);
  const [dictionaryInfoOpen, setDictionaryInfoOpen] = useState(false);
  const [tableFullscreen, setTableFullscreen] = useState(false);
  const [sectorSelectorOpen, setSectorSelectorOpen] = useState(false);
  const [sectorDropdownOpen, setSectorDropdownOpen] = useState(false);
  const dictionaryInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    setLocalDatasets(uploadedDatasets);
    setDatasetStatuses((prev) => syncDatasetStatuses(prev, uploadedDatasets.length));
    setActiveDsIdx((idx) => Math.min(idx, Math.max(0, uploadedDatasets.length - 1)));
  }, [uploadedDatasets]);

  const selectedSector = normalizeSector(detectedSector) ?? "finance";
  const recommendedSector = normalizeSector(sectorContext?.sector) ?? selectedSector;
  const selectedSectorInfo = SECTOR_LABELS[selectedSector] ?? { icon: "📊", label: selectedSector };
  const recommendedSectorInfo = SECTOR_LABELS[recommendedSector] ?? { icon: "📊", label: recommendedSector };
  const hasManualSectorOverride = selectedSector !== recommendedSector;
  const sectorUiText = lang === "fr"
    ? {
        detectedSector: "Secteur détecté",
        selectedSector: "Secteur choisi",
        recommendedBadge: "Recommandé",
        selectedBadge: "Sélectionné",
        infoTitle: "Comment le secteur est choisi ?",
        infoBody:
          "Le secteur est détecté automatiquement à partir de votre use case. Si la recommandation ne correspond pas à votre besoin, vous pouvez détailler davantage le use case ou sélectionner le secteur manuellement.",
        backToUseCase: "Détailler le use case",
        changeSectorAction: "Choisir manuellement",
        chooseAnotherSector: "Sélectionner un secteur",
      }
    : {
        detectedSector: "Detected sector",
        selectedSector: "Selected sector",
        recommendedBadge: "Recommended",
        selectedBadge: "Selected",
        infoTitle: "How is the sector selected?",
        infoBody:
          "The sector is automatically detected from your use case. If this recommendation does not match your need, you can refine the use case or choose the sector manually.",
        backToUseCase: "Refine use case",
        changeSectorAction: "Choose manually",
        chooseAnotherSector: "Select a sector",
      };
  const activeDs   = localDatasets[activeDsIdx] ?? { fileName: "", columns: [] };
  const activeDatasetStatus = datasetStatuses[activeDsIdx] ?? createEmptyDatasetDictionaryStatus();
  const columns    = activeDs.columns;
  const visibleColumns = getVisibleDatasetColumns(columns);
  const datasetCompletion = localDatasets.map((uploadedDataset, index) => {
    const visibleDatasetColumns = getVisibleDatasetColumns(uploadedDataset.columns);
    const incompleteDatasetRows = getIncompleteDatasetRows(uploadedDataset.columns);

    return {
      index,
      fileName: uploadedDataset.fileName,
      visibleCount: visibleDatasetColumns.length,
      incompleteCount: incompleteDatasetRows.length,
      complete: visibleDatasetColumns.length > 0 && incompleteDatasetRows.length === 0,
    };
  });
  const allDatasetsComplete = datasetCompletion.length > 0 && datasetCompletion.every((item) => item.complete);
  const totalIncompleteRows = datasetCompletion.reduce((sum, item) => sum + item.incompleteCount, 0);
  const showDatasetCompletionPanel = localDatasets.length > 1 && attemptedNext && !allDatasetsComplete;

  const persistDatasets = (next: UploadedDataset[]) => {
    updateDataset({
      columns: next[0]?.columns ?? [],
      uploadedDatasets: next,
    } as never);
    return next;
  };

  const updateColumn = (colIdx: number, field: string, value: string) => {
    setLocalDatasets((prev) => {
      const next = prev.map((ds, di) => {
        if (di !== activeDsIdx) return ds;
        const updatedCols = ds.columns.map((col, ci) =>
          ci === colIdx ? ({ ...col, [field]: value } as ColumnMetadata) : col
        );
        return { ...ds, columns: updatedCols };
      });
      return persistDatasets(next);
    });
  };

  const targetCol = visibleColumns.find(({ col }) => col.semanticType === "target")?.col;
  const incompleteRows = getIncompleteDatasetRows(columns);
  const incompleteRowIndexes = new Set(incompleteRows.map((row) => row.index));
  const metadataComplete = visibleColumns.length > 0 && incompleteRows.length === 0;
  const showValidationWarnings = attemptedNext && !metadataComplete;
  const extraMetadataKeys = Array.from(
    visibleColumns.reduce((acc, { col }) => {
      Object.keys(col as unknown as Record<string, unknown>).forEach((key) => {
        if (isExtraMetadataKey(key)) acc.add(key);
      });
      return acc;
    }, new Set<string>()),
  ).sort((a, b) => {
    const indexA = EXTRA_KEY_ORDER.indexOf(a);
    const indexB = EXTRA_KEY_ORDER.indexOf(b);
    if (indexA !== -1 || indexB !== -1) {
      if (indexA === -1) return 1;
      if (indexB === -1) return -1;
      return indexA - indexB;
    }
    return a.localeCompare(b);
  });
  const displayedExtraMetadataKeys = extraMetadataKeys.filter((key) =>
    visibleColumns.some(({ col }) => shouldShowExtraFieldForType(key, (col.semanticType as SemanticType) ?? "category")),
  );

  const applyDictionaryToDataset = (
    entries: DictionaryEntry[],
    targetDatasetIndex: number,
  ): { matched: number; remaining: number; backup: UploadedDataset[] | null } => {
    const dictionaryByOriginalName = new Map<string, DictionaryEntry>();
    for (const entry of entries) {
      dictionaryByOriginalName.set(normalizeText(entry.originalName), entry);
    }

    let matched = 0;
    let updated = 0;
    let added = 0;
    let remaining = 0;
    let backup: UploadedDataset[] | null = null;

    if (targetDatasetIndex < 0 || targetDatasetIndex >= localDatasets.length) {
      return { matched: 0, remaining: 0, backup: null };
    }

    const next = localDatasets.map((ds, datasetIndex) => {
      if (datasetIndex !== targetDatasetIndex) return ds;

      const existingByKey = new Set(ds.columns.map((column) => normalizeText(column.originalName)));

      const updatedColumns = ds.columns.map((column) => {
        const match = dictionaryByOriginalName.get(normalizeText(column.originalName));
        if (!match) return column;

        matched += 1;

        let changed = false;
        const nextColumn: ColumnMetadata = { ...column };

        if (match.businessName?.trim()) {
          nextColumn.businessName = match.businessName.trim();
          changed = true;
        }
        if (match.semanticType) {
          nextColumn.semanticType = match.semanticType;
          changed = true;
        }
        if (match.description?.trim()) {
          nextColumn.description = match.description.trim();
          changed = true;
        }
        if (match.extras) {
          for (const [extraKey, extraValue] of Object.entries(match.extras)) {
            if (!isExtraMetadataKey(extraKey)) continue;
            (nextColumn as unknown as Record<string, unknown>)[extraKey] = extraValue;
            changed = true;
          }
        }

        if (changed) {
          updated += 1;
        }

        return nextColumn;
      });

      for (const entry of entries) {
        const originalName = entry.originalName.trim();
        const key = normalizeText(originalName);
        if (!key || existingByKey.has(key) || isUnnamedColumn(originalName)) {
          continue;
        }

        updatedColumns.push({
          originalName,
          businessName: entry.businessName?.trim() || originalName,
          semanticType: entry.semanticType ?? "category",
          description: entry.description?.trim() ?? "",
          missingPercent: 0,
        });

        if (entry.extras) {
          for (const [extraKey, extraValue] of Object.entries(entry.extras)) {
            if (!isExtraMetadataKey(extraKey)) continue;
            (updatedColumns[updatedColumns.length - 1] as unknown as Record<string, unknown>)[extraKey] = extraValue;
          }
        }

        existingByKey.add(key);
        matched += 1;
        added += 1;
      }

      return { ...ds, columns: updatedColumns };
    });

    const updatedColumns = next[targetDatasetIndex]?.columns ?? [];
    remaining = updatedColumns
      .filter((column) => !isUnnamedColumn(column.originalName))
      .filter((column) => !isColumnComplete(column)).length;

    if (matched === 0) {
      return { matched: 0, remaining: 0, backup: null };
    }

    backup = cloneUploadedDatasets(localDatasets);
    setLocalDatasets(next);
    persistDatasets(next);

    const affected = updated + added;
    const toastCount = affected > 0 ? affected : matched;
    toast.success(`${t("dictionaryApplied", lang)} ${toastCount}.`);
    return { matched, remaining, backup };
  };

  const applyDictionaryToActiveDataset = (entries: DictionaryEntry[]) => {
    const datasetIndexTarget = activeDsIdx;
    return applyDictionaryToDataset(entries, datasetIndexTarget);
  };

  const handleUndoDictionaryImport = () => {
    if (!activeDatasetStatus.undoSnapshot) return;

    const restored = cloneUploadedDatasets(activeDatasetStatus.undoSnapshot);
    setLocalDatasets(restored);
    persistDatasets(restored);
    setDatasetStatuses((prev) =>
      prev.map((status, index) =>
        index === activeDsIdx ? createEmptyDatasetDictionaryStatus() : status,
      ),
    );
    toast.success(t("dictionaryImportCanceled", lang));
  };

  const handleDictionaryUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const datasetIndexTarget = activeDsIdx;
    const datasetNameTarget = localDatasets[activeDsIdx]?.fileName ?? "dataset";

    try {
      if (!currentProjectId) {
        throw new Error(t("dictionaryProjectRequired", lang));
      }

      setDatasetStatuses((prev) =>
        prev.map((status, index) =>
          index === datasetIndexTarget ? { ...status, error: null } : status,
        ),
      );
      const uploadResult = await uploadDatasetDictionary(currentProjectId, file, datasetNameTarget);
      const content = await file.text();
      const lowerName = file.name.toLowerCase();

      const rows = lowerName.endsWith(".json")
        ? parseJsonDictionary(JSON.parse(content))
        : parseDelimitedDictionary(content);

      const entries = rows
        .map(toDictionaryEntry)
        .filter((entry): entry is DictionaryEntry => entry !== null);

      if (entries.length === 0) {
        throw new Error(t("dictionaryParseError", lang));
      }

      setDatasetStatuses((prev) =>
        prev.map((status, index) =>
          index === datasetIndexTarget
            ? {
                ...status,
                storedDictionaryPath: uploadResult.stored_path,
                storedDictionaryName: file.name,
                storedDictionaryEntries: entries.map((entry) => ({ ...entry, extras: entry.extras ? { ...entry.extras } : undefined })),
              }
            : status,
        ),
      );

      const result = applyDictionaryToDataset(entries, datasetIndexTarget);
      if (result.matched === 0) {
        const message = t("dictionaryNoMatches", lang);
        setDatasetStatuses((prev) =>
          prev.map((status, index) =>
            index === datasetIndexTarget ? { ...status, error: message } : status,
          ),
        );
        toast.error(message);
        return;
      }

      setDatasetStatuses((prev) =>
        prev.map((status, index) =>
          index === datasetIndexTarget
            ? {
                fileName: file.name,
                summary: { matched: result.matched, remaining: result.remaining },
                error: null,
                undoSnapshot: result.backup,
                storedDictionaryPath: uploadResult.stored_path,
                storedDictionaryName: file.name,
                storedDictionaryEntries: entries.map((entry) => ({ ...entry, extras: entry.extras ? { ...entry.extras } : undefined })),
              }
            : status,
        ),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : t("dictionaryUploadBackendError", lang);
      setDatasetStatuses((prev) =>
        prev.map((status, index) =>
          index === datasetIndexTarget ? { ...status, error: message } : status,
        ),
      );
      toast.error(message);
    } finally {
      event.target.value = "";
    }
  };

  const handleReapplyStoredDictionary = () => {
    const entries = activeDatasetStatus.storedDictionaryEntries;
    if (!entries || entries.length === 0) {
      toast.error(t("dictionaryNoStored", lang));
      return;
    }

    const result = applyDictionaryToActiveDataset(entries);
    if (result.matched === 0) {
      const message = t("dictionaryNoMatches", lang);
      setDatasetStatuses((prev) =>
        prev.map((status, index) =>
          index === activeDsIdx ? { ...status, error: message } : status,
        ),
      );
      toast.error(message);
      return;
    }

    setDatasetStatuses((prev) =>
      prev.map((status, index) =>
        index === activeDsIdx
          ? {
              ...status,
              fileName: status.storedDictionaryName,
              summary: { matched: result.matched, remaining: result.remaining },
              error: null,
              undoSnapshot: result.backup,
            }
          : status,
      ),
    );
  };

  const handleNext = async () => {
    setAttemptedNext(true);
    if (!allDatasetsComplete) {
      toast.error(`${t("metadataRequiredDescription", lang)} (${totalIncompleteRows})`);
      return;
    }

    if (!currentProjectId) {
      toast.error(t("dictionaryProjectRequired", lang));
      return;
    }

    const toBackendColumns = (columns: ColumnMetadata[]): DatasetMetadataColumnUpdate[] => {
      return columns
        .filter((column) => !isUnnamedColumn(column.originalName))
        .map((column) => {
          const payload: DatasetMetadataColumnUpdate = {
            original_name: column.originalName,
            business_name: column.businessName,
            semantic_type: column.semanticType,
            description: column.description ?? "",
          };

          for (const [key, value] of Object.entries(column as unknown as Record<string, unknown>)) {
            if (!isExtraMetadataKey(key)) continue;
            if (value === undefined || value === null) continue;
            if (typeof value === "string" && !value.trim()) continue;
            payload[key] = value;
          }

          return payload;
        });
    };

    try {
      for (const ds of localDatasets) {
        if (!ds.datasetId || ds.datasetId.startsWith("restored-")) {
          continue;
        }

        await updateDatasetMetadata(currentProjectId, ds.datasetId, toBackendColumns(ds.columns));
      }

      await updateProject(currentProjectId, {
        business_rules: businessRules,
        detected_sector: selectedSector,
        status: "METADATA_CONFIGURED",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : t("dictionaryUploadBackendError", lang);
      toast.error(message);
      return;
    }

    setOnboardingStep(4);
  };

  return (
    <div className="max-w-6xl mx-auto animate-fade-in">
      <h2 className="text-xl font-bold text-primary mb-6">{t("metadataTitle", lang)}</h2>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 space-y-4">

          {/* ── Sélecteur de dataset si plusieurs ── */}
          {localDatasets.length > 1 && (
            <div className="flex items-center gap-3 bg-muted rounded-lg px-4 py-2">
              <button
                onClick={() => setActiveDsIdx((i) => Math.max(0, i - 1))}
                disabled={activeDsIdx === 0}
                aria-label={t("dictionaryPrevDataset", lang)}
                title={t("dictionaryPrevDataset", lang)}
                className="p-1 rounded hover:bg-primary/10 disabled:opacity-30 transition-colors"
              >
                <ChevronLeft size={18} className="text-primary" />
              </button>
              <div className="flex-1 text-center">
                <span className="text-sm font-semibold text-foreground">{activeDs.fileName}</span>
                <span className="text-xs text-muted-foreground ml-2">({activeDsIdx + 1} / {localDatasets.length})</span>
              </div>
              <button
                onClick={() => setActiveDsIdx((i) => Math.min(localDatasets.length - 1, i + 1))}
                disabled={activeDsIdx === localDatasets.length - 1}
                aria-label={t("dictionaryNextDataset", lang)}
                title={t("dictionaryNextDataset", lang)}
                className="p-1 rounded hover:bg-primary/10 disabled:opacity-30 transition-colors"
              >
                <ChevronRight size={18} className="text-primary" />
              </button>
            </div>
          )}

          {showDatasetCompletionPanel && (
            <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-foreground">
                  {t("dictionaryStatusTitle", lang)}
                </p>
                <p className="text-xs text-muted-foreground">
                  {datasetCompletion.filter((item) => item.complete).length} / {datasetCompletion.length}
                </p>
              </div>
              <div className="space-y-2">
                {datasetCompletion.map((item) => {
                  const itemStatus = datasetStatuses[item.index] ?? createEmptyDatasetDictionaryStatus();
                  return (
                    <button
                      key={`${item.fileName}-${item.index}`}
                      type="button"
                      onClick={() => setActiveDsIdx(item.index)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left transition-colors ${
                        item.index === activeDsIdx ? "border-primary bg-primary/5" : "border-border hover:border-primary/30"
                      }`}
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">{item.fileName}</p>
                        <p className="text-xs text-muted-foreground">
                          {item.complete
                            ? t("dictionaryStatusComplete", lang)
                            : `${item.incompleteCount} ${t("dictionaryStatusIncompleteRows", lang)}`}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className={`text-xs font-semibold ${item.complete ? "text-emerald-600" : "text-amber-700"}`}>
                          {item.complete ? "OK" : t("dictionaryStatusPending", lang)}
                        </p>
                        {itemStatus.fileName && (
                          <p className="max-w-[180px] truncate text-[11px] text-muted-foreground">{itemStatus.fileName}</p>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-foreground">{t("dictionaryUploadTitle", lang)}</span>
                <Popover open={dictionaryInfoOpen} onOpenChange={setDictionaryInfoOpen}>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex h-7 w-7 items-center justify-center rounded-full border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                      aria-label={t("dictionaryFormatInfo", lang)}
                      title={t("dictionaryFormatInfo", lang)}
                    >
                      <Info size={14} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="top" align="start" className="w-[360px] max-w-[92vw] space-y-2 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">{t("dictionaryFormatInfo", lang)}</p>
                      <button
                        type="button"
                        onClick={() => setDictionaryInfoOpen(false)}
                        className="inline-flex h-6 w-6 items-center justify-center rounded border border-border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                        aria-label={t("closeLabel", lang)}
                        title={t("closeLabel", lang)}
                      >
                        <X size={14} />
                      </button>
                    </div>
                    <p className="text-xs text-muted-foreground">{t("dictionaryAcceptedFormats", lang)}</p>
                    <pre className="overflow-x-auto rounded bg-muted px-2 py-2 text-[11px] leading-5 text-foreground">
{`[
  {
    "originalName": "customer_id",
    "businessName": "Identifiant client",
    "semanticType": "identifier",
    "description": "Identifiant unique du client"
  }
]`}
                    </pre>
                  </PopoverContent>
                </Popover>
              </div>
              <div className="flex items-center gap-2">
                <input
                  ref={dictionaryInputRef}
                  type="file"
                  accept=".json,.csv,.tsv,text/csv,application/json,text/tab-separated-values"
                  className="hidden"
                  title={t("uploadDictionary", lang)}
                  onChange={handleDictionaryUpload}
                />
                <button
                  type="button"
                  onClick={() => dictionaryInputRef.current?.click()}
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-primary px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/5 transition-colors"
                >
                  <FileUp size={16} />
                  {t("uploadDictionary", lang)}
                </button>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              {`${t("dictionaryApplyToDataset", lang)}: ${activeDs.fileName || "-"}`}
            </p>

            {activeDatasetStatus.fileName && activeDatasetStatus.summary && (
              <div className="flex items-start justify-between gap-3 rounded-lg bg-muted px-3 py-2 text-xs text-foreground">
                <div className="min-w-0">
                  <span className="font-semibold">{activeDatasetStatus.fileName}</span>
                  <span className="ml-2">{t("dictionaryMatched", lang)} {activeDatasetStatus.summary.matched}</span>
                  <span className="ml-3">{t("dictionaryRemaining", lang)} {activeDatasetStatus.summary.remaining}</span>
                </div>
                {activeDatasetStatus.undoSnapshot && (
                  <button
                    type="button"
                    onClick={handleUndoDictionaryImport}
                    className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-background hover:text-foreground transition-colors"
                    aria-label={t("dictionaryUndoImportMetadata", lang)}
                    title={t("dictionaryUndoImportMetadata", lang)}
                  >
                    <X size={12} />
                  </button>
                )}
              </div>
            )}

            {activeDatasetStatus.undoSnapshot && activeDatasetStatus.summary == null && (
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={handleUndoDictionaryImport}
                  className="inline-flex h-6 w-6 items-center justify-center rounded-md border border-border text-muted-foreground hover:bg-background hover:text-foreground transition-colors"
                  aria-label={t("dictionaryUndoImportMetadata", lang)}
                  title={t("dictionaryUndoImportMetadata", lang)}
                >
                  <X size={12} />
                </button>
              </div>
            )}

            {activeDatasetStatus.error && (
              <div className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <p>{activeDatasetStatus.error}</p>
              </div>
            )}
          </div>

          {showValidationWarnings && (
            <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-semibold">{t("metadataRequiredTitle", lang)}</p>
                <p className="text-sm">{t("metadataRequiredDescription", lang)}</p>
              </div>
            </div>
          )}

          {/* ── Tableau des colonnes ── */}
          <div className={`${tableFullscreen ? "fixed inset-4 z-50 bg-card rounded-xl overflow-hidden border border-border shadow-2xl" : "rounded-xl overflow-hidden border border-border shadow-sm"}`}>
            <div className="bg-dxc-midnight px-4 py-2 flex items-center justify-between gap-3">
              <span className="text-dxc-peach font-semibold text-sm">{t("describeData", lang)}</span>
              <button
                type="button"
                onClick={() => setTableFullscreen((prev) => !prev)}
                className="inline-flex h-7 w-7 items-center justify-center rounded border border-dxc-royal/40 text-dxc-sky hover:bg-white/10 transition-colors"
                aria-label={tableFullscreen ? t("metadataExitFullscreen", lang) : t("metadataEnterFullscreen", lang)}
                title={tableFullscreen ? t("metadataExitFullscreen", lang) : t("metadataEnterFullscreen", lang)}
              >
                {tableFullscreen ? <Minimize2 size={13} /> : <Maximize2 size={13} />}
              </button>
            </div>
            <div className={`${tableFullscreen ? "h-[calc(100%-40px)] overflow-auto" : "overflow-x-auto"}`}>
              <table className={`${tableFullscreen ? "min-w-[1500px]" : "w-full"} text-xs`}>
                <thead>
                  <tr className="bg-muted">
                    <th className={`px-3 py-2 text-left text-foreground font-semibold ${tableFullscreen ? "min-w-[300px]" : ""}`}>{t("originalName", lang)}</th>
                    <th className={`px-3 py-2 text-left text-foreground font-semibold ${tableFullscreen ? "min-w-[340px]" : ""}`}>{t("businessName", lang)} *</th>
                    <th className={`px-3 py-2 text-left text-foreground font-semibold ${tableFullscreen ? "min-w-[140px]" : ""}`}>{t("type", lang)} *</th>
                    <th className={`px-3 py-2 text-left text-foreground font-semibold ${tableFullscreen ? "min-w-[420px]" : ""}`}>Description *</th>
                    {displayedExtraMetadataKeys.map((key) => (
                      <th key={key} className={`px-3 py-2 text-left text-foreground font-semibold ${getExtraColumnWidthClass(key, tableFullscreen)}`}>
                        {formatExtraMetadataKeyLabel(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {visibleColumns.map(({ col, index: i }) => {
                    const semType = (col.semanticType as SemanticType) ?? "category";
                    const badge   = TYPE_BADGES[semType] ?? TYPE_BADGES["category"];
                    const rowIncomplete = showValidationWarnings && incompleteRowIndexes.has(i);
                    const missingBusinessName = showValidationWarnings && !col.businessName.trim();
                    const missingDescription = showValidationWarnings && !(col.description ?? "").trim();
                    return (
                      <tr key={`${col.originalName}-${i}`} className={`border-b border-border ${rowIncomplete ? "bg-amber-50" : semType === "target" ? "bg-dxc-melon/10" : "bg-card"}`}>
                        <td className="px-3 py-2">
                          <span className="bg-muted text-foreground font-mono text-xs px-2 py-0.5 rounded">
                            {semType === "target" && "🎯 "}{col.originalName}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={col.businessName}
                            onChange={(e) => updateColumn(i, "businessName", e.target.value)}
                            required
                            aria-label={`${t("businessName", lang)} ${col.originalName}`}
                            title={`${t("businessName", lang)} ${col.originalName}`}
                            className={`bg-transparent border-b outline-none text-foreground w-full py-1 ${missingBusinessName ? "border-red-500 focus:border-red-500" : "border-primary/30 focus:border-primary"}`}
                            placeholder={t("metadataBusinessNamePlaceholder", lang)}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={semType}
                            onChange={(e) => updateColumn(i, "semanticType", e.target.value)}
                            required
                            aria-label={`${t("type", lang)} ${col.originalName}`}
                            title={`${t("type", lang)} ${col.originalName}`}
                            className={`text-xs rounded px-2 py-1 font-semibold border-0 cursor-pointer ${badge.className}`}
                          >
                            {(Object.entries(TYPE_BADGES) as [SemanticType, typeof TYPE_BADGES[SemanticType]][]).map(([key, b]) => (
                              <option key={key} value={key}>{b.icon} {b.label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={(col as never as { description?: string }).description ?? ""}
                            onChange={(e) => updateColumn(i, "description" as keyof ColumnMetadata, e.target.value)}
                            required
                            aria-label={`Description ${col.originalName}`}
                            title={`Description ${col.originalName}`}
                            className={`bg-transparent border-b outline-none text-foreground w-full py-1 ${missingDescription ? "border-red-500 focus:border-red-500" : "border-primary/30 focus:border-primary"}`}
                            placeholder={t("metadataDescriptionPlaceholder", lang)}
                          />
                        </td>
                        {displayedExtraMetadataKeys.map((key) => {
                          const isVisibleForType = shouldShowExtraFieldForType(key, semType);
                          const value = ((col as unknown as Record<string, unknown>)[key] as string | undefined) ?? "";
                          return (
                            <td key={`${col.originalName}-${key}`} className={`px-3 py-2 ${getExtraColumnWidthClass(key, tableFullscreen)}`}>
                              {isVisibleForType ? (
                                <input
                                  value={value}
                                  onChange={(e) => updateColumn(i, key, e.target.value)}
                                  aria-label={`${formatExtraMetadataKeyLabel(key)} ${col.originalName}`}
                                  title={`${formatExtraMetadataKeyLabel(key)} ${col.originalName}`}
                                  className="bg-transparent border-b border-primary/30 focus:border-primary outline-none text-foreground w-full py-1"
                                  placeholder={formatExtraMetadataKeyLabel(key)}
                                />
                              ) : (
                                <span className="text-muted-foreground/60">-</span>
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-semibold text-foreground">{t("businessRules", lang)}</label>
            <textarea
              value={businessRules}
              onChange={(e) => updateDataset({ businessRules: e.target.value })}
              rows={3}
              className="w-full rounded-lg border border-border bg-muted p-3 text-foreground text-sm placeholder:text-muted-foreground focus:border-primary focus:outline-none"
              placeholder={t("businessRulesPlaceholder", lang)}
            />
          </div>
        </div>

        {/* ── Panneau récapitulatif (sans qualité) ── */}
        <div className="lg:col-span-2">
          <div className="bg-dxc-midnight rounded-xl p-5 space-y-3 sticky top-32">
            <h3 className="text-dxc-peach font-bold text-sm">{t("systemUnderstands", lang)}</h3>
            <div className="space-y-2 text-xs">
              {targetCol && (
                <p className="text-white">✅ {t("targetVariable", lang)} : "{targetCol.businessName}" →{" "}
                  <span className="bg-dxc-melon text-white px-1.5 py-0.5 rounded text-xs font-semibold">{t("binaryClassification", lang)}</span>
                </p>
              )}
              <p className="text-white">✅ {visibleColumns.filter(({ col }) => !["identifier", "target", "ignore"].includes(col.semanticType)).length} {t("usableFeatures", lang)}</p>
              <p className="text-white">✅ {visibleColumns.filter(({ col }) => col.semanticType === "date").length} {t("temporalFeatures", lang)}</p>
              <p className="text-white">✅ {visibleColumns.filter(({ col }) => col.semanticType === "numeric").length} colonnes numériques</p>
              <p className="text-white">✅ {visibleColumns.filter(({ col }) => col.semanticType === "category").length} colonnes texte / catégorie</p>
              {visibleColumns.filter(({ col }) => col.semanticType === "identifier").map(({ col: c }) => (
                <p key={c.originalName} className="text-dxc-gold">⚠️ "{c.originalName}" {t("autoExcluded", lang)}</p>
              ))}
              {localDatasets.length > 1 && (
                <p className="text-dxc-sky">📊 {localDatasets.length} sources de données</p>
              )}
            </div>

            <div className="mt-4 pt-4 border-t border-dxc-royal/30 text-center space-y-1">
              <div className="inline-flex items-center gap-2 bg-dxc-royal text-white px-4 py-2 rounded-lg font-semibold text-sm">
                {hasManualSectorOverride ? selectedSectorInfo.icon : recommendedSectorInfo.icon} {hasManualSectorOverride ? sectorUiText.selectedSector : sectorUiText.detectedSector} : {hasManualSectorOverride ? selectedSectorInfo.label : recommendedSectorInfo.label}
                <span className="rounded bg-white/20 px-2 py-0.5 text-[10px] uppercase tracking-wide">
                  {hasManualSectorOverride ? sectorUiText.selectedBadge : sectorUiText.recommendedBadge}
                </span>
                <Popover>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-white/40 text-white/90 hover:bg-white/10"
                      aria-label={sectorUiText.infoTitle}
                      title={sectorUiText.infoTitle}
                    >
                      <Info size={12} />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="top" align="center" className="w-[320px] max-w-[92vw] p-3 text-left">
                    <p className="text-sm font-semibold text-foreground">{sectorUiText.infoTitle}</p>
                    <p className="mt-2 text-xs text-muted-foreground">{sectorUiText.infoBody}</p>
                    <div className="mt-3 flex items-center justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => setOnboardingStep(1)}
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        {sectorUiText.backToUseCase}
                      </button>
                      <button
                        type="button"
                        onClick={() => setSectorSelectorOpen(true)}
                        className="text-xs font-semibold text-primary hover:underline"
                      >
                        {sectorUiText.changeSectorAction}
                      </button>
                    </div>
                  </PopoverContent>
                </Popover>
              </div>

              {sectorSelectorOpen && (
                <div className="mx-auto mt-2 max-w-[280px] space-y-2 text-left">
                  <div className="flex items-center justify-between gap-2">
                    <label className="block text-[11px] text-dxc-sky">{sectorUiText.chooseAnotherSector}</label>
                    <button
                      type="button"
                      onClick={() => setSectorSelectorOpen(false)}
                      className="inline-flex h-5 w-5 items-center justify-center rounded border border-dxc-royal/40 text-dxc-sky hover:text-dxc-peach hover:bg-white/10 transition-colors"
                      aria-label={t("closeLabel", lang)}
                      title={t("closeLabel", lang)}
                    >
                      <X size={11} />
                    </button>
                  </div>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setSectorDropdownOpen((o) => !o)}
                      className="flex w-full items-center justify-between rounded-md border border-dxc-royal/40 bg-dxc-midnight px-2 py-1.5 text-xs text-white hover:border-dxc-peach focus:outline-none"
                    >
                      <span>{SECTOR_LABELS[selectedSector]?.icon} {SECTOR_LABELS[selectedSector]?.label}</span>
                      <ChevronDown size={12} className={`ml-1 shrink-0 transition-transform ${sectorDropdownOpen ? "rotate-180" : ""}`} />
                    </button>
                    {sectorDropdownOpen && (
                      <div className="absolute z-50 mt-1 max-h-44 w-full overflow-y-auto rounded-md border border-dxc-royal/40 bg-dxc-midnight shadow-lg text-xs text-white">
                        {SUPPORTED_SECTORS.map((sector) => (
                          <button
                            key={sector}
                            type="button"
                            onClick={() => { updateDataset({ detectedSector: sector as Sector }); setSectorDropdownOpen(false); }}
                            className={`flex w-full items-center justify-between px-2 py-1.5 text-left transition-colors hover:bg-dxc-royal/30 ${selectedSector === sector ? "bg-dxc-royal/40" : ""}`}
                          >
                            <span>{SECTOR_LABELS[sector].icon} {SECTOR_LABELS[sector].label}</span>
                            {sector === recommendedSector && (
                              <span className="ml-2 shrink-0 rounded bg-white/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-dxc-peach">
                                {sectorUiText.recommendedBadge}
                              </span>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {sectorContext && !hasManualSectorOverride && (
              <div className="mt-4 pt-4 border-t border-dxc-royal/30 space-y-2 text-left">
                <p className="text-dxc-peach text-xs font-semibold">Sector Detection Agent</p>
                <p className="text-white text-xs">
                  Confidence: {(sectorContext.confidence * 100).toFixed(1)}%
                </p>
                <p className="text-dxc-sky text-xs">
                  Focus: {sectorContext.dashboard_focus}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="flex justify-between pt-6">
        <button onClick={() => setOnboardingStep(2)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button
          onClick={handleNext}
          className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors"
        >
          {t("next", lang)} →
        </button>
      </div>
    </div>
  );
}