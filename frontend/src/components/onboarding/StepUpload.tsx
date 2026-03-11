import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileCheck, Trash2, Plus, Loader2, AlertCircle } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { t } from "@/lib/i18n";
import { uploadDataset, type UploadResponse } from "@/lib/datasetsApi";

interface UploadedFile {
  name:         string;
  datasetId:    string;
  rowCount:     number;
  columnCount:  number;
  qualityScore: number;
  preview:      Record<string, unknown>[];
  columns:      { original_name: string; detected_type: string; null_percent: number }[];
}

export function StepUpload() {
  const { updateDataset, setOnboardingStep, userPreferences } = useAppStore();
  const lang = userPreferences.language;

  const [uploading, setUploading]         = useState(false);
  const [progress, setProgress]           = useState(0);
  const [files, setFiles]                 = useState<UploadedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);
  const [error, setError]                 = useState<string | null>(null);

  const handleUpload = useCallback(
    async (file: File) => {
      const projectId = useAppStore.getState().currentProjectId;
      if (!projectId) {
        setError("Aucun projet actif — retournez à l'étape 1.");
        return;
      }

      setUploading(true);
      setProgress(10);
      setError(null);

      try {
        const progressInterval = setInterval(() => {
          setProgress((p) => (p < 85 ? p + 5 : p));
        }, 200);

        const result: UploadResponse = await uploadDataset(projectId, file);
        clearInterval(progressInterval);
        setProgress(100);

        const newFile: UploadedFile = {
          name:         file.name,
          datasetId:    result.file_id,
          rowCount:     result.row_count,
          columnCount:  result.column_count,
          qualityScore: result.quality_score,
          preview:      result.preview,
          columns:      result.columns,
        };

        // ── Calculer les valeurs AVANT setFiles ──────────────────────────
        const currentFiles = useAppStore.getState ? files : [];
        const next         = [...files, newFile];
        const totalRows    = next.reduce((s, f) => s + f.rowCount, 0);
        const totalCols    = next.reduce((s, f) => s + f.columnCount, 0);
        const avgQuality   = Math.round(next.reduce((s, f) => s + f.qualityScore, 0) / next.length);
        const newIdx       = next.length - 1;

        // ── Zustand en premier (hors render) ─────────────────────────────
        updateDataset({
          fileName:       next.map((f) => f.name).join(", "),
          rowCount:       totalRows,
          columnCount:    totalCols,
          qualityScore:   avgQuality,
          detectedSector: (result.detected_sector as never) ?? "general",
          previewData:    result.preview,
        });

        // ── React state ensuite ──────────────────────────────────────────
        setFiles(next);
        setActiveFileIdx(newIdx);

      } catch (err) {
        setError(err instanceof Error ? err.message : "Erreur lors de l'upload");
      } finally {
        setUploading(false);
        setTimeout(() => setProgress(0), 800);
      }
    },
    [files, updateDataset],
  );

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      acceptedFiles.forEach((file) => handleUpload(file));
    },
    [handleUpload],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "application/json": [".json"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    },
    multiple: true,
    disabled: uploading,
  });

  const removeFile = (idx: number) => {
    const next = files.filter((_, i) => i !== idx);
    if (next.length === 0) {
      updateDataset({ fileName: "", rowCount: 0, columnCount: 0, qualityScore: 0, previewData: [] });
      setActiveFileIdx(0);
    } else {
      const newIdx     = Math.min(activeFileIdx, next.length - 1);
      const totalRows  = next.reduce((s, f) => s + f.rowCount, 0);
      const totalCols  = next.reduce((s, f) => s + f.columnCount, 0);
      const avgQuality = Math.round(next.reduce((s, f) => s + f.qualityScore, 0) / next.length);
      updateDataset({ fileName: next.map((f) => f.name).join(", "), rowCount: totalRows, columnCount: totalCols, qualityScore: avgQuality, previewData: next[newIdx].preview });
      setActiveFileIdx(newIdx);
    }
    setFiles(next);
  };

  const activeFile = files[activeFileIdx];
  const hasFiles   = files.length > 0;

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h2 className="text-xl font-bold text-primary">{t("uploadTitle", lang)}</h2>

      {/* ── Dropzone ── */}
      <div
        {...getRootProps()}
        className={`bg-card rounded-xl shadow-sm border-2 border-dashed text-center cursor-pointer transition-all ${
          hasFiles ? "p-6" : "p-8 md:p-12"
        } ${isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/30 hover:border-primary"} ${uploading ? "opacity-60 pointer-events-none" : ""}`}
      >
        <input {...getInputProps()} />
        {hasFiles ? (
          <div className="flex items-center justify-center gap-3">
            <Plus className="text-primary" size={20} />
            <span className="text-sm font-medium text-foreground">{t("addAnotherSource", lang)}</span>
            <span className="text-xs text-muted-foreground">CSV, Excel, JSON</span>
          </div>
        ) : (
          <>
            <Upload className="mx-auto text-primary mb-4" size={48} />
            <p className="text-lg font-bold text-foreground">{t("dragFilesHere", lang)}</p>
            <p className="text-sm text-muted-foreground mt-1">{t("fileFormats", lang)}</p>
            <button
              className="mt-4 px-6 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:opacity-90 transition-colors"
              onClick={(e) => { e.stopPropagation(); open(); }}
            >
              {t("browseFiles", lang)}
            </button>
          </>
        )}
      </div>

      {/* ── Progress ── */}
      {uploading && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" />
            <span>Upload en cours…</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-dxc-melon rounded-full transition-all duration-200" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-muted-foreground text-center">{progress}%</p>
        </div>
      )}

      {/* ── Error ── */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm">
          <AlertCircle size={16} className="shrink-0" />
          {error}
        </div>
      )}

      {/* ── File tabs ── */}
      {hasFiles && (
        <>
          <div className="flex gap-2 flex-wrap">
            {files.map((file, i) => (
              <div
                key={`${file.name}-${i}`}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all ${
                  i === activeFileIdx ? "border-primary bg-primary/5" : "border-border bg-card hover:border-primary/30"
                }`}
                onClick={() => setActiveFileIdx(i)}
              >
                <FileCheck className="text-primary shrink-0" size={14} />
                <span className="text-xs font-medium text-foreground truncate max-w-[140px]">{file.name}</span>
                <span className="text-xs text-muted-foreground">{file.rowCount.toLocaleString()} {t("lines", lang)}</span>
                <button
                  onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                  className="text-muted-foreground/50 hover:text-destructive transition-colors ml-1 min-w-[28px] min-h-[28px] flex items-center justify-center"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>

          {activeFile && (
            <>
              <div className="bg-card rounded-xl shadow-sm border border-border p-5 flex items-center gap-4">
                <FileCheck className="text-primary shrink-0" size={24} />
                <div className="flex-1">
                  <p className="font-semibold text-foreground">{activeFile.name}</p>
                  <div className="flex gap-2 mt-1">
                    <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded font-medium">{activeFile.rowCount.toLocaleString()} {t("rows", lang)}</span>
                    <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded font-medium">{activeFile.columnCount} {t("cols", lang)}</span>
                  </div>
                </div>
                <div className="relative w-14 h-14">
                  <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                    <circle cx="18" cy="18" r="15.5" fill="none" className="stroke-muted" strokeWidth="3" />
                    <circle cx="18" cy="18" r="15.5" fill="none"
                      stroke={activeFile.qualityScore > 70 ? "#004AAC" : activeFile.qualityScore > 40 ? "#FFAE41" : "#D14600"}
                      strokeWidth="3"
                      strokeDasharray={`${activeFile.qualityScore} ${100 - activeFile.qualityScore}`}
                      strokeLinecap="round"
                    />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-foreground">{activeFile.qualityScore}</span>
                </div>
              </div>

              {activeFile.preview.length > 0 && (
                <div className="rounded-xl overflow-hidden border border-border shadow-sm">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="bg-dxc-midnight">
                          {activeFile.columns.map((col) => (
                            <th key={col.original_name} className="px-3 py-2 text-left text-dxc-peach font-bold text-xs whitespace-nowrap">{col.original_name}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {activeFile.preview.map((row, i) => (
                          <tr key={i} className={i % 2 === 0 ? "bg-card" : "bg-muted"}>
                            {activeFile.columns.map((col) => (
                              <td key={col.original_name} className="px-3 py-2 text-foreground whitespace-nowrap">{String(row[col.original_name] ?? "")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">{t("columnQuality", lang)}</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {activeFile.columns.map((col) => (
                    <div key={col.original_name} className="bg-card rounded-lg p-2 border border-border">
                      <span className="text-xs font-mono text-muted-foreground">{col.original_name}</span>
                      <div className="h-1.5 bg-muted rounded-full mt-1 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${100 - col.null_percent}%`, background: col.null_percent > 5 ? "#FF7E51" : "#004AAC" }} />
                      </div>
                      <span className="text-xs text-muted-foreground">{col.null_percent.toFixed(1)}% {t("missing", lang)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </>
      )}

      <div className="flex justify-between pt-4">
        <button onClick={() => setOnboardingStep(1)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button
          onClick={() => setOnboardingStep(3)}
          disabled={!hasFiles || uploading}
          className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t("next", lang)} →
        </button>
      </div>
    </div>
  );
}