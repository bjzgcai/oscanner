/**
 * Normalize text for matching - handles punctuation variations
 * Converts smart quotes, em-dashes, etc. to standard ASCII equivalents
 */
export function normalizeForMatching(text: string): string {
  return text
    .toLowerCase()
    // Smart quotes to straight quotes
    .replace(/[\u201C\u201D]/g, '"')    // Smart double quotes (U+201C, U+201D) → straight double quote
    .replace(/[\u2018\u2019]/g, "'")    // Smart single quotes (U+2018, U+2019) → straight single quote
    // Dashes to hyphen
    .replace(/[\u2014\u2013]/g, '-')    // Em-dash (U+2014), en-dash (U+2013) → hyphen
    // Ellipsis to three dots
    .replace(/\u2026/g, '...');          // Ellipsis (U+2026) → three dots
}

/**
 * Find phrase in text with normalization
 * Returns the index in the original text, or -1 if not found
 */
export function findNormalizedPhrase(text: string, phrase: string): number {
  const normalizedText = normalizeForMatching(text);
  const normalizedPhrase = normalizeForMatching(phrase);

  const index = normalizedText.indexOf(normalizedPhrase);
  return index;
}
