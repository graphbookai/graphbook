from textwrap import dedent


def convert_to_md(docstring: str) -> str:
    # docstring = docstring.strip()
    docstring = dedent(docstring)
    lines = docstring.split("\n")
    md = ""
    bold_key = False
    for line in lines:
        if line.strip() == "Args:":
            md += "**Parameters**"
            bold_key = True
        elif line.strip() == "Returns:":
            md += "**Returns**"
            bold_key = False
        elif line.strip() == "Raises:":
            md += "**Raises**"
            bold_key = False
        else:
            if bold_key:
                entry = line.split(":")
                if len(entry) > 1:
                    key = entry[0].strip()
                    value = entry[1].strip()
                    md += f"- **{key}**: {value}"
            else:
                md += line
        md += "\n"
    md = md.strip()

    return md
