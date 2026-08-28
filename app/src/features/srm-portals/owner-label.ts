export function formatOwnerLabel(name?: string, username?: string): string {
  const person = (name ?? "").trim();
  const jobNo = (username ?? "").trim();
  if (person && jobNo && person !== jobNo) {
    return `${person}（${jobNo}）`;
  }
  return person || jobNo;
}

export function resolveOwnerDisplayName(
  userId: string,
  candidates: Array<{ userId: string; name: string; username?: string }>,
  fallback?: { userId: string; name: string; username?: string; storedName?: string }
): string {
  const selected = candidates.find((item) => item.userId === userId);
  if (selected) {
    return formatOwnerLabel(selected.name, selected.username);
  }
  if (fallback && userId === fallback.userId) {
    return formatOwnerLabel(fallback.name, fallback.username);
  }
  return (fallback?.storedName ?? "").trim();
}
