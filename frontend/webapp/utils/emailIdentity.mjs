const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function isValidEmail(value) {
  return EMAIL_RE.test(String(value || '').trim().toLowerCase());
}

export function parseEmailList(value) {
  const parts = String(value || '')
    .replace(/\n/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const emails = [];
  const invalidEmails = [];
  const seen = new Set();

  for (const part of parts) {
    const normalized = part.toLowerCase();
    if (!isValidEmail(normalized)) {
      invalidEmails.push(part);
      continue;
    }
    if (!seen.has(normalized)) {
      seen.add(normalized);
      emails.push(normalized);
    }
  }

  return { emails, invalidEmails };
}

export function formatEmailListError(invalidEmails) {
  if (!invalidEmails || invalidEmails.length === 0) return '';
  return `Invalid email format: ${invalidEmails.join(', ')}`;
}
