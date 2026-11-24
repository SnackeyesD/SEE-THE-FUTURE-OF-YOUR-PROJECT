/** Téléchargement local d'un texte, sans réseau ni dépendance Tauri. */
export function downloadText(
  filename: string,
  content: string,
  mime = "text/markdown;charset=utf-8",
): boolean {
  return downloadBlob(filename, new Blob([content], { type: mime }));
}

/** Décode une charge base64 (export binaire validé par le sidecar) et la télécharge. */
export function downloadBase64(filename: string, contentBase64: string, mime: string): boolean {
  try {
    const binary = atob(contentBase64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return downloadBlob(filename, new Blob([bytes], { type: mime }));
  } catch {
    return false;
  }
}

function downloadBlob(filename: string, blob: Blob): boolean {
  try {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    return true;
  } catch {
    return false;
  }
}
