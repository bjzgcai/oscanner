export const DIMENSION_KEYS = ['spec_quality', 'cloud_architecture', 'ai_engineering', 'mastery_professionalism'];

const aliases: Record<string, string[]> = {
  spec_quality: ['spec_quality', '\u89c4\u8303\u4e0e\u5185\u5efa\u8d28\u91cf', 'technical_capability'],
  cloud_architecture: ['cloud_architecture', '\u4e91\u539f\u751f\u4e0e\u67b6\u6784\u6f14\u8fdb'],
  ai_engineering: ['ai_engineering', 'AI\u5de5\u7a0b\u4e0e\u81ea\u52a8\u6f14\u8fdb', 'ai_engineering_capability'],
  mastery_professionalism: ['mastery_professionalism', '\u5de5\u7a0b\u4fee\u517b\u4e0e\u804c\u4e1a\u7d20\u517b', 'professionalism', 'mastery_professionalism_collaboration'],
};

export function numericScore(value: unknown): number | null {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const nested = value as Record<string, unknown>;
    return numericScore(nested.score ?? nested.value ?? nested.total);
  }
  if (typeof value !== 'number' && !(typeof value === 'string' && value.trim())) return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 && number <= 100 ? number : null;
}

export function canonicalScores(input: unknown): Record<string, number | null> {
  const scores = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  return Object.fromEntries(DIMENSION_KEYS.map(key => {
    const alias = aliases[key].find(name => Object.prototype.hasOwnProperty.call(scores, name));
    return [key, alias ? numericScore(scores[alias]) : null];
  }));
}

export function averageScore(input: unknown): number | null {
  const values = Object.values(canonicalScores(input));
  return values.every(value => value !== null) ? values.reduce((sum, value) => sum + value, 0) / 4 : null;
}

export function levelFromScore(score: number | null): string | null {
  if (score === null || numericScore(score) === null) return null;
  if (score >= 85) return 'L5';
  if (score >= 70) return 'L4';
  if (score >= 50) return 'L3';
  if (score >= 30) return 'L2';
  return 'L1';
}

export function trajectoryScores(input: unknown, plugin: string): Record<string, number | null> {
  const scores = input && typeof input === 'object' ? input as Record<string, unknown> : {};
  return plugin === 'zgc_ai_native_2026' ? canonicalScores(input) : Object.fromEntries(
    Object.entries(scores).filter(([key]) => key !== 'reasoning').map(([key, value]) => [key, numericScore(value)]));
}
