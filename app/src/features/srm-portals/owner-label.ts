export function formatOwnerLabel(name?: string, username?: string): string {
  const person = (name ?? "").trim();
  const jobNo = (username ?? "").trim();
  if (person && jobNo && person !== jobNo) {
    return `${person}（${jobNo}）`;
  }
  return person || jobNo;
}
