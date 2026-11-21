/** The hex value of design tokens from `index.css`, for code that cannot take a class name (the
    confetti canvas). Tokens that are missing or not hex are left out, so the caller falls back to
    its own default rather than to a literal colour (DEF-013). */
export function tokenHex(...names: string[]): string[] {
  const style = getComputedStyle(document.documentElement);
  return names
    .map((n) => style.getPropertyValue(`--color-${n}`).trim())
    .filter((v) => /^#[0-9a-f]{3,8}$/i.test(v));
}
