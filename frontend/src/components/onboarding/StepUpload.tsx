import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileCheck, Trash2, Plus } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { detectSector, getColumnsForSector, generatePreviewData } from "@/lib/mockData";
import type { ColumnMetadata } from "@/types/app";
import { t } from "@/lib/i18n";

interface UploadedFile {
  name: string;
  rowCount: number;
  columns: ColumnMetadata[];
  previewData: Record<string, unknown>[];
  qualityScore: number;
}

export function StepUpload() {
  const { onboarding, updateDataset, setOnboardingStep, userPreferences } = useAppStore();
  const lang = userPreferences.language;
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [activeFileIdx, setActiveFileIdx] = useState(0);

  const simulateUpload = useCallback(
    (name: string) => {
      setUploading(true);
      setProgress(0);
      const sector = detectSector(onboarding.useCaseDescription);
      const cols = getColumnsForSector(sector);
      const data = generatePreviewData(cols);
      const rowCount = Math.round(Math.random() * 40000 + 10000);
      const qualityScore = Math.round(Math.random() * 20 + 75);

      const interval = setInterval(() => {
        setProgress((p) => {
          if (p >= 100) {
            clearInterval(interval);
            setUploading(false);
            const newFile: UploadedFile = { name, rowCount, columns: cols, previewData: data, qualityScore };
            setFiles((prev) => {
              const next = [...prev, newFile];
              setActiveFileIdx(next.length - 1);
              const allColumns = next.flatMap((f) => f.columns);
              const uniqueColumns = allColumns.filter((col, idx, arr) => arr.findIndex((c) => c.originalName === col.originalName) === idx);
              const totalRows = next.reduce((sum, f) => sum + f.rowCount, 0);
              const avgQuality = Math.round(next.reduce((sum, f) => sum + f.qualityScore, 0) / next.length);
              updateDataset({ fileName: next.map((f) => f.name).join(", "), rowCount: totalRows, columnCount: uniqueColumns.length, columns: uniqueColumns, qualityScore: avgQuality, detectedSector: sector, previewData: next[next.length - 1].previewData });
              return next;
            });
            return 100;
          }
          return p + 4;
        });
      }, 50);
    },
    [onboarding.useCaseDescription, updateDataset]
  );

  const onDrop = useCallback((acceptedFiles: File[]) => { acceptedFiles.forEach((file) => simulateUpload(file.name)); }, [simulateUpload]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"], "application/json": [".json"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    multiple: true,
  });

  const removeFile = (idx: number) => {
    setFiles((prev) => {
      const next = prev.filter((_, i) => i !== idx);
      if (next.length === 0) {
        updateDataset({ fileName: "", rowCount: 0, columnCount: 0, columns: [], qualityScore: 0, previewData: [] });
        setActiveFileIdx(0);
      } else {
        const newIdx = Math.min(activeFileIdx, next.length - 1);
        setActiveFileIdx(newIdx);
        const sector = detectSector(onboarding.useCaseDescription);
        const allColumns = next.flatMap((f) => f.columns);
        const uniqueColumns = allColumns.filter((col, i, arr) => arr.findIndex((c) => c.originalName === col.originalName) === i);
        const totalRows = next.reduce((sum, f) => sum + f.rowCount, 0);
        const avgQuality = Math.round(next.reduce((sum, f) => sum + f.qualityScore, 0) / next.length);
        updateDataset({ fileName: next.map((f) => f.name).join(", "), rowCount: totalRows, columnCount: uniqueColumns.length, columns: uniqueColumns, qualityScore: avgQuality, detectedSector: sector, previewData: next[newIdx].previewData });
      }
      return next;
    });
  };

  const activeFile = files[activeFileIdx];
  const hasFiles = files.length > 0;

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h2 className="text-xl font-bold text-primary">{t("uploadTitle", lang)}</h2>

      <div
        {...getRootProps()}
        className={`bg-card rounded-xl shadow-sm border-2 border-dashed text-center cursor-pointer transition-all ${
          hasFiles ? "p-6" : "p-8 md:p-12"
        } ${isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/30 hover:border-primary"}`}
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
              onClick={(e) => { e.stopPropagation(); simulateUpload("dataset_clients_2025.csv"); }}
            >
              {t("browseFiles", lang)}
            </button>
          </>
        )}
      </div>

      {uploading && (
        <div className="space-y-2">
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div className="h-full bg-dxc-melon rounded-full transition-all duration-100" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-muted-foreground text-center">{progress}%</p>
        </div>
      )}

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
                <button onClick={(e) => { e.stopPropagation(); removeFile(i); }} className="text-muted-foreground/50 hover:text-destructive transition-colors ml-1 min-w-[28px] min-h-[28px] flex items-center justify-center" aria-label={`${t("delete", lang)} ${file.name}`}>
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
                    <span className="text-xs bg-muted text-muted-foreground px-2 py-0.5 rounded font-medium">{activeFile.columns.length} {t("cols", lang)}</span>
                  </div>
                </div>
                <div className="relative w-14 h-14">
                  <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                    <circle cx="18" cy="18" r="15.5" fill="none" className="stroke-muted" strokeWidth="3" />
                    <circle cx="18" cy="18" r="15.5" fill="none" stroke={activeFile.qualityScore > 70 ? "#004AAC" : activeFile.qualityScore > 40 ? "#FFAE41" : "#D14600"} strokeWidth="3" strokeDasharray={`${activeFile.qualityScore} ${100 - activeFile.qualityScore}`} strokeLinecap="round" />
                  </svg>
                  <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-foreground">{activeFile.qualityScore}</span>
                </div>
              </div>

              <div className="rounded-xl overflow-hidden border border-border shadow-sm">
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="bg-dxc-midnight">
                        {activeFile.columns.map((col) => (
                          <th key={col.originalName} className="px-3 py-2 text-left text-dxc-peach font-bold text-xs whitespace-nowrap">{col.originalName}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {activeFile.previewData.map((row, i) => (
                        <tr key={i} className={i % 2 === 0 ? "bg-card" : "bg-muted"}>
                          {activeFile.columns.map((col) => (
                            <td key={col.originalName} className="px-3 py-2 text-foreground whitespace-nowrap">{String(row[col.originalName] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-foreground">{t("columnQuality", lang)}</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                  {activeFile.columns.map((col) => (
                    <div key={col.originalName} className="bg-card rounded-lg p-2 border border-border">
                       <span className="text-xs font-mono text-muted-foreground">{col.originalName}</span>
                      <div className="h-1.5 bg-muted rounded-full mt-1 overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${100 - col.missingPercent}%`, background: col.missingPercent > 5 ? "#FF7E51" : "#004AAC" }} />
                      </div>
                      <span className="text-xs text-muted-foreground">{col.missingPercent}% {t("missing", lang)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {files.length > 1 && (
            <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 flex items-center gap-4 flex-wrap">
              <div className="text-xs text-primary font-semibold">📊 {files.length} {t("dataSources", lang)}</div>
              <div className="flex gap-3 text-xs text-muted-foreground">
                <span>{useAppStore.getState().dataset.rowCount.toLocaleString()} {t("totalLines", lang)}</span>
                <span>{useAppStore.getState().dataset.columnCount} {t("uniqueColumns", lang)}</span>
                <span>{t("avgQuality", lang)} : {useAppStore.getState().dataset.qualityScore}/100</span>
              </div>
            </div>
          )}
        </>
      )}

      <div className="flex justify-between pt-4">
        <button onClick={() => setOnboardingStep(1)} className="px-6 py-2 text-primary border border-primary rounded-lg hover:bg-primary/5 transition-colors">
          ← {t("back", lang)}
        </button>
        <button
          onClick={() => setOnboardingStep(3)}
          disabled={!hasFiles}
          className="px-8 py-3 rounded-lg font-semibold text-primary-foreground bg-primary hover:opacity-90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {t("next", lang)} →
        </button>
      </div>
    </div>
  );
}
