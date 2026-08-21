from frugal.agents import BaseAgent
import re

# NOTE: This is intended as an example of subclassing BaseAgent
#       it is NOT a general markdown to LaTeX converter of which
#       there are many better examples you can use for ideas when
#       building your own.

def protect_math(text):
    math_blocks = []

    def repl(match):
        math_blocks.append(match.group(0))
        return f"__MATH_{len(math_blocks)-1}__"

    # Protect \( ... \), \[ ... \], and $ ... $
    text = re.sub(r'\\\(.*?\\\)', repl, text)
    text = re.sub(r'\\\[.*?\\\]', repl, text)
    text = re.sub(r'\$.*?\$', repl, text)

    return text, math_blocks


def restore_math(text, math_blocks):
    for i, block in enumerate(math_blocks):
        text = text.replace(f"__MATH_{i}__", block)
    return text


def convert_markdown_tables(lines):
    output = []
    i = 0
    n = len(lines)

    def is_table_separator(line):
        return re.match(r'^\s*\|?[\-\:\s]+\|[\-\|\:\s]*$', line)

    def split_row(line):
        # Remove leading/trailing |
        line = line.strip().strip('|')
        cells = [c.strip() for c in line.split('|')]
        return cells

    def escape_cell(text):
        # Decode HTML entity first
        text = text.replace("&amp;", "&")
        # Escape LaTeX unless math
        if not re.search(r"\$.*?\$", text):
            text = re.sub(r"(?<!\\)&", r"\\&", text)
        return text

    while i < n:
        line = lines[i]

        # Detect table start
        if '|' in line and i + 1 < n and is_table_separator(lines[i + 1]):

            header_line = line
            separator_line = lines[i + 1]

            headers = split_row(header_line)
            num_cols = len(headers)

            # Alignment: default left
            col_format = "l" * num_cols

            i += 2  # move past header + separator

            rows = []
            while i < n and '|' in lines[i]:
                rows.append(split_row(lines[i]))
                i += 1

            # Build a LaTeX table
            output.append(r"\begin{tabular}{" + col_format + "}")
            output.append(r"\hline")

            # Header row
            header_cells = [
                r"\textbf{" + escape_cell(c) + "}" for c in headers
            ]
            output.append(" & ".join(header_cells) + r" \\")
            output.append(r"\hline")

            # Data rows
            for row in rows:
                # pad row if needed
                if len(row) < num_cols:
                    row += [""] * (num_cols - len(row))

                row_cells = [escape_cell(c) for c in row]
                output.append(" & ".join(row_cells) + r" \\")

            output.append(r"\hline")
            output.append(r"\end{tabular}")

        else:
            output.append(line)
            i += 1

    return output

def convert_markdown_to_latex(lines):
    output = []
    list_stack = []  # track nested list types ("itemize", "enumerate")

    def close_lists(target_depth=0):
        while len(list_stack) > target_depth:
            env = list_stack.pop()
            output.append(f"\\end{{{env}}}")

    def open_list(env):
        list_stack.append(env)
        output.append(f"\\begin{{{env}}}")

    def detect_list_type(line):
        if re.match(r"\s*[-*]\s+", line):
            return "itemize"
        elif re.match(r"\s*\d+\.\s+", line):
            return "enumerate"
        return None

    def get_indent_level(line):
        match = re.match(r"^(\s*)", line)
        if not match:
            return 0

        indent = match.group(1)

        # Normalize tabs → spaces (important)
        indent = indent.replace("\t", "    ")

        return len(indent)

    def apply_inline_formatting(text):
        # Protect math FIRST
        text, math_blocks = protect_math(text)

        # Bold
        text = re.sub(r"\*\*(.*?)\*\*", r"\\textbf{\1}", text)

        # Italic (avoid matching inside words like Z^*)
        text = re.sub(r"(?<!\w)\*(.*?)\*(?!\w)", r"\\textit{\1}", text)

        # Convert math delimiters AFTER math protection
        text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text)

        # Restore math untouched
        text = restore_math(text, math_blocks)

        return text

    def replace_mu(text):
        # Case 1: μ followed by unit letter (μs, μm, μF, etc.)
        text = re.sub(r"μ([a-zA-Z])", r"\\textmu \1", text)

        # Case 2: standalone μ (fallback)
        text = text.replace("μ", r"\textmu ")

        return text

    def normalize_unicode(text):
        text = text.replace("–", "--")
        text = text.replace("—", "---")
        text = text.replace("−", "-")
        text = text.replace("***", "---")

        text = text.replace("✅", " $\\checkmark$ ")
        text = text.replace("❌", " $\\times$ ")
        text = text.replace("≤", " $\\le$ ")
        text = text.replace("∝", " $\\propto ")
        text = text.replace("≪", "$\\ll$")
        text = text.replace("≥", "$\\geq$")
        text = text.replace("φ", "$\\varphi$")
        text = text.replace("≫", "$\\gg$")
        text = text.replace("Δ", "$\\Delta$")
        text = text.replace("≈", r"$\approx$")
        # μ handled separately (smarter rule below)
        text = replace_mu(text)

        return text
    
    def decode_html_entities(text):
        return text.replace("&amp;", "&")

    def escape_latex(text, in_table=False):
        # Split into math and non-math regions
        parts = re.split(r"(\${1,2}.*?\${1,2}|\\\[.*?\\\])", text)

        for i in range(len(parts)):
            part = parts[i]

            # Skip math segments entirely
            if re.match(r"^\${1,2}.*\${1,2}$", part) or re.match(r"^\\\[.*\\\]$", part):
                continue

            # Apply escaping ONLY to non-math text
            part = (
                part
                .replace("#", r"\#")
                .replace("%", r"\%")
            )
            #    .replace("_", r"\_") # heuristic - usually don't want to escape this...

            if not in_table:
                part = re.sub(r"(?<!\\)&", r"\\&", part)

            parts[i] = part

        return "".join(parts)



    heading_map = {
        1: r"\section*",
        2: r"\subsection*",
        3: r"\subsubsection*",
        4: r"\paragraph",
        5: r"\subparagraph"
    }

    prev_indent = 0
    in_table = False
    prev_indent = 0

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        line = re.sub(r"[\u00A0\u2009\u202F]", " ", line) # purge unusual spaces

        # Markdown does not support nested tables so this is sufficient
        if line.strip().startswith(r"\begin{tabular}"):
            in_table = True

        elif line.strip().startswith(r"\end{tabular}"):
            in_table = False
        
        
        # Normalize unicode
        line = normalize_unicode(line)
        line = decode_html_entities(line)

        if not in_table:

            # Horizontal rule
            if re.match(r"^\s*---\s*$", line):
                close_lists()
                output.append(r"\hrule")
                continue

            # Headers
            header_match = re.match(r"^(#{1,5})\s+(.*)", line)
            if header_match:
                close_lists()
                level = len(header_match.group(1))
                content = apply_inline_formatting(header_match.group(2))

                content = escape_latex(content,in_table) # fix latex 

                output.append(f"{heading_map[level]}{{{content}}}")
                continue

            # List detection
            list_type = detect_list_type(line)
            #indent = get_indent_level(line)
            list_match = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)

            if list_match:
                indent = len(list_match.group(1).replace("\t", "    "))
                list_marker = list_match.group(2)
                content = list_match.group(3)

                list_type = "itemize" if list_marker in ["-", "*"] else "enumerate"

            if list_type:
                depth = indent // 2  # assume 2 spaces per level

                # Normalize impossible jumps
                if depth > len(list_stack):
                    depth = len(list_stack)

                # Open exactly ONE level when needed
                if depth == len(list_stack):
                    open_list(list_type)

                # Close extra levels
                while len(list_stack) > depth + 1:
                    close_lists(len(list_stack) - 1)

                # Handle type switch
                if list_stack and list_stack[-1] != list_type:
                    close_lists(depth)
                    open_list(list_type)

                # Ensure base list exists
                if not list_stack:
                    open_list(list_type)

                # Extract content
                content = re.sub(r"^\s*([-*]|\d+\.)\s+", "", line)
                content = apply_inline_formatting(content)

                # --- Child detection ---
                has_child = False
                try:
                    next_line = lines[i + 1]
                    next_indent = get_indent_level(next_line)
                    has_child = next_indent > indent
                except (IndexError, NameError):
                    pass

                # --- Label handling ---
                label_match = re.match(r"^([^:]+:)\s+(.*)", content)

                if label_match and not has_child and depth==0:
                    label = label_match.group(1)
                    desc = label_match.group(2)

                    label = escape_latex(label, in_table)
                    desc = escape_latex(desc, in_table)

                    output.append(
                        f"\\item \\textbf{{{label}}} \\\\\n\\textit{{{desc}}}"
                    )
                else:
                    content = escape_latex(content, in_table)
                    output.append(f"\\item {content}")

                continue

            else:
                # close any open lists
                close_lists()


        # Display math preserved
        if re.match(r"\\\[(.*?)\\\]", line):
            line = escape_latex(line,in_table) # fix LaTex
            output.append(line)
            continue

        # Apply inline formatting to normal text
        line = apply_inline_formatting(line)
        line = escape_latex(line,in_table) # fix LaTex

        output.append(line)

    # Close any remaining lists
    close_lists()

    return "\n".join(output)



class MD2LaTeXAgent(BaseAgent):
    def __init__(self, azure_openai_client, config):
        super().__init__(azure_openai_client, config)

    def prompt(self, user_prompt: str):
        lines = user_prompt.split('\n')

        lines = convert_markdown_tables(lines)
        latex = convert_markdown_to_latex(lines)
        return latex
    
