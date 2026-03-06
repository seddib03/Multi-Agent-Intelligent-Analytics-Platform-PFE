import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileCheck } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { detectSector, getColumnsForSector, generatePreviewData } from "@/lib/mockData";

export function StepUpload() {
  const { onboarding, updateDataset, setOnboardingStep } = useAppStore();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploaded, setUploaded] = useState(false);
  const [fileName, setFileName] = useState("");
  const [columns, setColumns] = useState<ReturnType<typeof getColumnsForSector>>([]);
  const [previewData, setPreviewData] = useState<Record<string, unknown>[]>([]);

  const simulateUpload = useCallback(
    (name: string) => {
      setFileName(name);
      setUploading(true);
      setProgress(0);

      const sector = detectSector(onboarding.useCaseDescription);
      const cols = getColumnsForSector(sector);
      const data = generatePreviewData(cols);
      const rowCount = Math.round(Math.random() * 40000 + 10000);

      const interval = setInterval(() => {
        setProgress((p) => {
          if (p >= 100) {
            clearInterval(interval);
            setUploading(false);
            setUploaded(true);
            setColumns(cols);
            setPreviewData(data);
            updateDataset({
              fileName: name,
              rowCount,
              columnCount: cols.length,
              columns: cols,
              qualityScore: Math.round(Math.random() * 20 + 75),
              detectedSector: sector,
              previewData: data,
            });
            return 100;
          }
          return p + 4;
        });
      }, 50);
    },
    [onboarding.useCaseDescription, updateDataset]
  );

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (acceptedFiles.length > 0) {
        simulateUpload(acceptedFiles[0].name);
      }
    },
    [simulateUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"], "application/json": [".json"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"] },
    maxFiles: 1,
  });

  const qualityScore = useAppStore((s) => s.dataset.qualityScore);

  return (
    <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">
      <h2 className="text-xl font-bold text-dxc-royal">Upload des données</h2>

      {!uploaded ? (
        <>
          <div
            {...getRootProps()}
            className={`bg-dxc-white rounded-xl shadow-sm border-2 border-dashed p-12 text-center cursor-pointer transition-all ${
              isDragActive ? "border-dxc-royal bg-[#EEF4FF]" : "border-dxc-sky hover:border-dxc-royal"
            }`}
          >
            <input {...getInputProps()} />
            <Upload className="mx-auto text-dxc-royal mb-4" size={48} />
            <p className="text-lg font-bold text-dxc-midnight">Glissez votre fichier ici</p>
            <p className="text-sm text-dxc-royal/60 mt-1">CSV, Excel (.xlsx), JSON — max 100 MB</p>
            <button
              className="mt-4 px-6 py-2 bg-dxc-royal text-dxc-white rounded-lg font-medium hover:bg-dxc-blue transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                simulateUpload("dataset_clients_2025.csv");
              }}
            >
              Parcourir mes fichiers
            </button>
          </div>

          {uploading && (
            <div className="space-y-2">
              <div className="h-2 bg-dxc-canvas rounded-full overflow-hidden">
                <div className="h-full bg-dxc-melon rounded-full transition-all duration-100" style={{ width: `${progress}%` }} />
              </div>
              <p className="text-xs text-dxc-royal/60 text-center">{progress}%</p>
            </div>
          )}
        </>
      ) : (
        <>
          {/* File info card */}
          <div className="bg-dxc-white rounded-xl shadow-sm border border-dxc-canvas p-5 flex items-center gap-4">
            <FileCheck className="text-dxc-royal shrink-0" size={24} />
            <div className="flex-1">
              <p className="font-semibold text-dxc-midnight">{fileName}</p>
              <div className="flex gap-2 mt-1">
                <span className="text-xs bg-dxc-canvas text-dxc-royal px-2 py-0.5 rounded font-medium">
                  {useAppStore.getState().dataset.rowCount.toLocaleString()} lignes
                </span>
                <span className="text-xs bg-dxc-canvas text-dxc-royal px-2 py-0.5 rounded font-medium">
                  {columns.length} colonnes
                </span>
              </div>
            </div>
            {/* Quality circle */}
            <div className="relative w-14 h-14">
              <svg viewBox="0 0 36 36" className="w-full h-full -rotate-90">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="#F6F3F0" strokeWidth="3" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none"
                  stroke={qualityScore > 70 ? "#004AAC" : qualityScore > 40 ? "#FFAE41" : "#D14600"}
                  strokeWidth="3"
                  strokeDasharray={`${qualityScore} ${100 - qualityScore}`}
                  strokeLinecap="round"
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xs font-bold text-dxc-midnight">{qualityScore}</span>
            </div>
          </div>

          {/* Data preview */}
          <div className="rounded-xl overflow-hidden border border-dxc-canvas shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-dxc-midnight">
                    {columns.map((col) => (
                      <th key={col.originalName} className="px-3 py-2 text-left text-dxc-peach font-bold text-[11px] whitespace-nowrap">
                        {col.originalName}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {previewData.map((row, i) => (
                    <tr key={i} className={i % 2 === 0 ? "bg-dxc-white" : "bg-dxc-canvas"}>
                      {columns.map((col) => (
                        <td key={col.originalName} className="px-3 py-2 text-dxc-midnight whitespace-nowrap">
                          {String(row[col.originalName] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Column quality */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-dxc-midnight">Qualité par colonne</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {columns.map((col) => (
                <div key={col.originalName} className="bg-dxc-white rounded-lg p-2 border border-dxc-canvas">
                  <span className="text-[10px] font-mono text-dxc-midnight/70">{col.originalName}</span>
                  <div className="h-1.5 bg-dxc-canvas rounded-full mt-1 overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${100 - col.missingPercent}%`,
                        background: col.missingPercent > 5 ? "#FF7E51" : "#004AAC",
                      }}
                    />
                  </div>
                  <span className="text-[9px] text-dxc-royal/50">{col.missingPercent}% manquant</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Navigation */}
      <div className="flex justify-between pt-4">
        <button onClick={() => setOnboardingStep(1)} className="px-6 py-2 text-dxc-royal border border-dxc-royal rounded-lg hover:bg-dxc-canvas transition-colors">
          ← Retour
        </button>
        <button
          onClick={() => setOnboardingStep(3)}
          disabled={!uploaded}
          className="px-8 py-3 rounded-lg font-semibold text-dxc-white bg-dxc-royal hover:bg-dxc-blue transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Suivant →
        </button>
      </div>
    </div>
  );
}
