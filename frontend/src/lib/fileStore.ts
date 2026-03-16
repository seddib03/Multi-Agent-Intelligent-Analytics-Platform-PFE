/**
 * Store mémoire pour les fichiers uploadés.
 * NON persisté — les File objects ne sont pas sérialisables en JSON.
 * Réinitialisé à chaque rechargement de page.
 */

interface FileEntry {
  file:      File;
  projectId: string;
  datasetId: string;
}

const _files: FileEntry[] = [];

export const fileStore = {
  add(entry: FileEntry) {
    const idx = _files.findIndex((f) => f.datasetId === entry.datasetId);
    if (idx >= 0) _files[idx] = entry;
    else _files.push(entry);
    // Toujours garder une référence "__last__" pour fallback
    const lastIdx = _files.findIndex((f) => f.projectId === "__last__");
    const lastEntry = { ...entry, projectId: "__last__" };
    if (lastIdx >= 0) _files[lastIdx] = lastEntry;
    else _files.push(lastEntry);
  },

  getByProject(projectId: string): File | null {
    // Chercher par projectId, sinon fallback sur le dernier fichier uploadé
    return (
      _files.find((f) => f.projectId === projectId)?.file ??
      _files.find((f) => f.projectId === "__last__")?.file ??
      null
    );
  },

  getAllByProject(projectId: string): File[] {
    const byProject = _files.filter((f) => f.projectId === projectId && f.projectId !== "__last__");
    if (byProject.length > 0) return byProject.map((f) => f.file);
    const last = _files.find((f) => f.projectId === "__last__");
    return last ? [last.file] : [];
  },

  getLastFile(): File | null {
    return _files.find((f) => f.projectId === "__last__")?.file ?? null;
  },

  clear() {
    _files.length = 0;
  },
};