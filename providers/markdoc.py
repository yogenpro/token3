"""Read Markdoc table/tab presentation as inert text, without executing tags.

The original response remains the source payload/hash. This view only restores
explicit headings and table cells for the existing document readers.
"""
import re


def table_markdown(body):
    if "{% table %}" not in body:
        return body
    output, cells, groups, in_table = [], [], [], False

    def row():
        nonlocal cells
        if cells:
            groups.append(cells)
            cells = []

    for raw in body.splitlines():
        line = raw.strip()
        if line == "{% table %}":
            if in_table:
                raise ValueError("Nested Markdoc table")
            in_table, cells, groups = True, [], []
        elif line == "{% /table %}":
            if not in_table:
                raise ValueError("Unmatched Markdoc table end")
            row()
            if not groups or not groups[0] or any(len(r) != len(groups[0]) for r in groups):
                raise ValueError("Incomplete Markdoc table")
            for index, values in enumerate(groups):
                if any("|" in value for value in values):
                    raise ValueError("Unsupported Markdoc pipe in table cell")
                output.append("| " + " | ".join(values) + " |")
                if index == 0:
                    output.append("| " + " | ".join("---" for _ in values) + " |")
            in_table = False
        elif in_table:
            if line == "---":
                row()
            elif line == "*" or line.startswith("* "):
                cells.append(line[2:])
            elif line and cells:
                cells[-1] += " " + line
            elif line:
                raise ValueError("Unrecognized Markdoc table cell")
        else:
            tab = re.fullmatch(r'{% tab title="([^"]+)" %}', line)
            if tab:
                output.append("### " + tab[1])
            elif line.startswith("## "):
                output.append(re.sub(r"\s*{% id=\"[^\"]+\" %}\s*$", "", line))
            else:
                output.append(raw)
    if in_table:
        raise ValueError("Unclosed Markdoc table")
    return "\n".join(output)
