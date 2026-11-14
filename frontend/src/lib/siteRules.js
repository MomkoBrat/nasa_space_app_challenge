// DATA_CONTRACT has no `recommendations` field, so derive it: polar sites are context-only.
// If the team later adds an explicit `recommendations` boolean, it takes precedence.
export function canRecommend(site) {
  if (!site) return false;
  if (typeof site.recommendations === 'boolean') return site.recommendations;
  return site.group !== 'polar';
}
