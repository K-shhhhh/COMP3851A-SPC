/* =========================================================
   SIMPLE MARKDOWN FOR AI RESPONSES

   Extracted from GroupStudyPage.jsx so both Study Group and
   Companion chat can render AI responses the same way, instead
   of each page needing its own copy.
   ========================================================= */

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
                  <th key={index}>{header}</th>
                ))}
              </tr>
            </thead>

            <tbody>
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
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
            <li key={index}>{item}</li>
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
            <li key={index}>{item}</li>
          ))}
        </ol>,
      );

      continue;
    }

    if (!line.trim()) {
      i += 1;
      continue;
    }

    blocks.push(
      <p key={`paragraph-${i}`}>
        {line}
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
