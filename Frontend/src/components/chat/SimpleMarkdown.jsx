/* =========================================================
   SIMPLE MARKDOWN FOR AI RESPONSES

   Extracted from GroupStudyPage.jsx so both Study Group and
   Companion chat can render AI responses the same way, instead
   of each page needing its own copy.
   ========================================================= */

/* Inline formatting inside one line of text: **bold**, *italic* and `code`.
   Built as React elements (never raw HTML), so a reply cannot inject markup.
   Anything that does not match a complete pair is shown as plain text. */
const INLINE_PATTERN = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\s][^*\n]*\*)/g;

function renderInline(text, keyPrefix) {
  return String(text)
    .split(INLINE_PATTERN)
    .map((part, index) => {
      const key = `${keyPrefix}-${index}`;

      if (part.length > 4 && part.startsWith("**") && part.endsWith("**")) {
        return <strong key={key}>{part.slice(2, -2)}</strong>;
      }

      if (part.length > 2 && part.startsWith("`") && part.endsWith("`")) {
        return <code key={key}>{part.slice(1, -1)}</code>;
      }

      if (part.length > 2 && part.startsWith("*") && part.endsWith("*")) {
        return <em key={key}>{part.slice(1, -1)}</em>;
      }

      return part;
    });
}

function SimpleMarkdown({ children = "" }) {
  const lines = String(children).split("\n");
  const blocks = [];

  for (let i = 0; i < lines.length; ) {
    const line = lines[i];

    // Markdown table
    if (
      /^\s*\|.*\|\s*$/.test(line) &&
      /^\s*\|?\s*:?-+/.test(lines[i + 1] || "")
    ) {
      const rows = [];

      const splitRow = (row) =>
        row
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((cell) => cell.trim());

      const headers = splitRow(line);

      i += 2;

      while (
        i < lines.length &&
        /^\s*\|.*\|\s*$/.test(lines[i])
      ) {
        rows.push(splitRow(lines[i]));
        i += 1;
      }

      blocks.push(
        <div
          className="markdown-table-wrap"
          key={`table-${i}`}
        >
          <table>
            <thead>
              <tr>
                {headers.map((header, index) => (
                  <th key={index}>
                    {renderInline(header, `th-${index}`)}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>
                      {renderInline(cell, `td-${rowIndex}-${cellIndex}`)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );

      continue;
    }

    // Bullet list
    if (/^\s*[-*+]\s+/.test(line)) {
      const items = [];

      while (
        i < lines.length &&
        /^\s*[-*+]\s+/.test(lines[i])
      ) {
        items.push(
          lines[i].replace(/^\s*[-*+]\s+/, ""),
        );

        i += 1;
      }

      blocks.push(
        <ul key={`ul-${i}`}>
          {items.map((item, index) => (
            <li key={index}>{renderInline(item, `uli-${index}`)}</li>
          ))}
        </ul>,
      );

      continue;
    }

    // Numbered list
    if (/^\s*\d+[.)]\s+/.test(line)) {
      const items = [];

      while (
        i < lines.length &&
        /^\s*\d+[.)]\s+/.test(lines[i])
      ) {
        items.push(
          lines[i].replace(/^\s*\d+[.)]\s+/, ""),
        );

        i += 1;
      }

      blocks.push(
        <ol key={`ol-${i}`}>
          {items.map((item, index) => (
            <li key={index}>{renderInline(item, `oli-${index}`)}</li>
          ))}
        </ol>,
      );

      continue;
    }

    if (!line.trim()) {
      i += 1;
      continue;
    }

    // A heading line such as "## Title" is shown as bold text, without the
    // leading # characters.
    const heading = line.match(/^\s{0,3}#{1,6}\s+(.*)$/);

    if (heading) {
      blocks.push(
        <p key={`heading-${i}`}>
          <strong>{renderInline(heading[1], `h-${i}`)}</strong>
        </p>,
      );

      i += 1;
      continue;
    }

    blocks.push(
      <p key={`paragraph-${i}`}>
        {renderInline(line, `p-${i}`)}
      </p>,
    );

    i += 1;
  }

  return (
    <div className="markdown-content">
      {blocks}
    </div>
  );
}

export default SimpleMarkdown;
