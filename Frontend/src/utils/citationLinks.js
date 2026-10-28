export function citationViewerPath(source) {
  const noteId = Number(source?.note_id);
  const page = Math.max(1, Number(source?.page) || 1);
  const title = source?.note_title || "Study material";

  const params = new URLSearchParams({
    page: String(page),
    title,
  });

  return `/notes/${noteId}/view?${params.toString()}`;
}
