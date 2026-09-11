// Some scheme content (MyScheme-discovered schemes in particular — see
// ai_service/discovery/sources/myscheme.py) is stored as raw Markdown, often
// several paragraphs with **bold** notes and numbered clauses. That's fine in
// a full-detail view, but dumped straight into a summary card it reads as a
// wall of literal asterisks. These two helpers turn it into a clean,
// card-sized preview; nothing here mutates the stored value.

/** Strips the Markdown syntax that shows up literally in card text: bold/italic
 *  markers and collapsed whitespace/newlines. Not a full Markdown renderer —
 *  a card excerpt doesn't need real formatting, just to stop showing "**". */
export function stripMarkdown(text) {
  if (!text) return ''
  return String(text)
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/\*(.*?)\*/g, '$1')
    .replace(/^[-*]\s+/gm, '')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Truncates at a word boundary near maxChars, so a card never mid-cuts a word. */
export function excerpt(text, maxChars = 160) {
  const clean = stripMarkdown(text)
  if (clean.length <= maxChars) return clean
  const cut = clean.slice(0, maxChars)
  const lastSpace = cut.lastIndexOf(' ')
  return `${cut.slice(0, lastSpace > 0 ? lastSpace : maxChars)}…`
}
