/** Start a browser "Save as" for a blob and release the object URL afterwards. */
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  // Revoking in the same tick can cut the download off before the browser reads the blob.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** "CV_Title_Company.pdf" — underscores instead of anything Windows rejects in a name. */
export function fileName(...parts: Array<string | null | undefined>): string {
  const joined = parts
    .map((part) => (part ?? "").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, ""))
    .filter(Boolean)
    .join("_");
  return `${joined || "document"}.pdf`;
}
