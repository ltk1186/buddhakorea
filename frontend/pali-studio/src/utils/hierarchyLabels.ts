const stripDiacritics = (value: string): string => {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '');
};

const normalizeKey = (value: string): string => {
  return stripDiacritics(value.trim().toLowerCase());
};

const LABEL_KO_MAP: Record<string, string> = {
  vagga: '품',
  sutta: '경',
  nipata: '집',
  kanda: '칸다',
  pariccheda: '장',
  niddesa: '의석',
  vannana: '주해',
  katha: '카타',
  gatha: '게송',
  work: '전체',
  section: '절',
  subsection: '소절',
};

export const getHierarchyLabelKo = (raw: string | null | undefined, fallback: string): string => {
  if (!raw) return fallback;
  const mapped = LABEL_KO_MAP[normalizeKey(raw)];
  return mapped || fallback;
};

