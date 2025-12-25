import type { Literature } from '@/types/literature';

const TRAILING_PAREN_CONTENT_RE = /\(([^()]*)\)\s*$/;

const extractTrailingParenthetical = (value: string): string | null => {
  const match = value.match(TRAILING_PAREN_CONTENT_RE);
  const content = match?.[1]?.trim();
  return content ? content : null;
};

export const getLiteraturePrimaryTitle = (lit?: Literature | null): string => {
  if (!lit) return '';
  const rawName = (lit.name ?? '').trim();
  const extracted = rawName ? extractTrailingParenthetical(rawName) : null;
  if (extracted) return extracted;
  if (rawName) return rawName;

  const meta = lit.display_metadata ?? {};
  if (meta.ko_translit) return meta.ko_translit;
  if (lit.pali_name) return lit.pali_name;
  return lit.id;
};

export const buildLiteratureSecondaryLine = (lit?: Literature | null): string => {
  if (!lit) return '';
  const meta = lit.display_metadata ?? {};
  const parts: string[] = [];
  if (meta.abbr) parts.push(meta.abbr);
  if (lit.pali_name) parts.push(lit.pali_name);
  if (meta.ko_translit) parts.push(meta.ko_translit);
  return parts.join(' · ');
};
