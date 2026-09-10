"""Recognize Lua startup statements without interpreting user code.

Only complete, standalone literal calls are editable. The lexer distinguishes
strings/comments from code and tracks lexical block nesting. Anything outside
that grammar remains an inspectable, read-only entry.
"""
from __future__ import annotations

import dataclasses
import re

from .common import Error, digest, file_value, read_text, snapshot, source
from .desktop import enrich, identity


@dataclasses.dataclass
class Token:
    kind: str
    text: str
    start: int
    end: int
    depth: int = 0


def lex(text):
    tokens = []
    pos = 0
    stack = []
    pending_do = 0
    while pos < len(text):
        begin = pos
        c = text[pos]
        if c.isspace():
            pos += 1
            continue
        comment = text.startswith("--", pos)
        offset = pos + 2 if comment else pos
        long = re.match(r"\[(=*)\[", text[offset:])
        if long:
            close = "]" + long[1] + "]"
            end = text.find(close, offset + len(long[0]))
            if end < 0:
                tokens.append(Token("invalid", text[pos:], pos, len(text), len(stack)))
                break
            pos = end + len(close)
            kind = "comment" if comment else "string"
        elif comment:
            end = text.find("\n", pos)
            pos = len(text) if end < 0 else end
            kind = "comment"
        elif c in "\"'":
            pos += 1
            while pos < len(text):
                if text[pos] == "\\":
                    pos += 2
                elif text[pos] == c:
                    pos += 1
                    break
                else:
                    pos += 1
            pos = min(pos, len(text))
            kind = "string" if text[pos - 1:pos] == c else "invalid"
        elif c.isalpha() or c == "_":
            match = re.match(r"[A-Za-z_][A-Za-z_0-9]*", text[pos:])
            if not match:
                pos += 1
                kind = "invalid"
            else:
                pos += len(match[0])
                kind = "word"
        else:
            pos += 1
            kind = "punct"
        token = Token(kind, text[begin:pos], begin, pos, len(stack))
        tokens.append(token)
        if kind == "word":
            if token.text in ("function", "if", "for", "while", "repeat"):
                stack.append(token.text)
                if token.text in ("for", "while"):
                    pending_do += 1
            elif token.text == "do":
                if pending_do:
                    pending_do -= 1
                else:
                    stack.append("do")
            elif token.text in ("end", "until"):
                if stack:
                    stack.pop()
    return tokens


def literal(text):
    long = re.match(r"\[(=*)\[", text)
    if long:
        result = text[len(long[0]):-(len(long[1]) + 2)]
        return re.sub(r"^\r?\n", "", result)
    if len(text) < 2 or text[-1] != text[0]:
        raise Error("Unterminated Lua string.")
    content = text[1:-1]
    output = []
    pos = 0
    escapes = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
               "v": "\v", "\\": "\\", "\"": "\"", "'": "'", "\n": "\n"}
    while pos < len(content):
        if content[pos] != "\\":
            output.append(content[pos])
            pos += 1
            continue
        pos += 1
        if pos >= len(content):
            raise Error("Incomplete Lua escape.")
        char = content[pos]
        if char in escapes:
            output.append(escapes[char])
            pos += 1
        elif char == "z":
            pos += 1
            while pos < len(content) and content[pos].isspace():
                pos += 1
        elif char == "x" and re.match(r"[0-9a-fA-F]{2}", content[pos + 1:]):
            output.append(chr(int(content[pos + 1:pos + 3], 16)))
            pos += 3
        elif char.isdigit():
            digits = re.match(r"[0-9]{1,3}", content[pos:])[0]
            if int(digits) > 255:
                raise Error("Invalid Lua byte escape.")
            output.append(chr(int(digits)))
            pos += len(digits)
        else:
            raise Error("This Lua string escape is not supported for editing.")
    return "".join(output)


def parse(text):
    tokens = lex(text)
    code = [token for token in tokens if token.kind != "comment"]
    results = []
    for i, token in enumerate(code):
        if token.text not in ("o", "hl") or i + 3 >= len(code):
            continue
        dot, method, opening = code[i + 1:i + 4]
        if dot.text != "." or opening.text != "(":
            continue
        if method.text not in ("launch_on_start", "exec_on_start", "exec_cmd", "on"):
            continue
        if method.text == "on" and i + 4 < len(code) and "hyprland.start" not in code[i + 4].text:
            continue
        depth = 1
        end_index = i + 4
        while end_index < len(code) and depth:
            current = code[end_index]
            if current.kind != "string":
                depth += (current.text == "(") - (current.text == ")")
            end_index += 1
        closing = code[end_index - 1] if end_index > i + 4 else opening
        start = text.rfind("\n", 0, token.start) + 1
        line_end = text.find("\n", closing.end)
        line_end = len(text) if line_end < 0 else line_end
        span_end = closing.end
        suffix = text[span_end:line_end].strip()
        if suffix.startswith(";"):
            span_end += text[span_end:line_end].index(";") + 1
            suffix = text[span_end:line_end].strip()
        supported = (token.text == "o" and method.text in ("launch_on_start", "exec_on_start")
                     and token.depth == 0 and depth == 0 and end_index == i + 6
                     and code[i + 4].kind == "string" and not text[start:token.start].strip()
                     and (not suffix or suffix.startswith("--")))
        command = text[token.start:closing.end]
        problem = "Only standalone, top-level literal startup calls can be changed safely."
        if supported:
            try:
                command = literal(code[i + 4].text)
                problem = "" if command and "\0" not in command else "Empty or invalid startup command."
            except Error as exc:
                problem = str(exc)
        results.append(dict(start=start, end=span_end, command=command, enabled=True,
                            readOnly=problem, line=text.count("\n", 0, token.start) + 1,
                            fragment=text[start:span_end]))
    # Recognize only whole comment lines, never calls embedded in prose or long comments.
    for token in tokens:
        if token.kind != "comment" or token.depth or "\n" in token.text or re.match(r"--\[=*\[", token.text):
            continue
        if token.text.startswith("-- omastart:off "):
            continue  # Managed blocks are decoded as a whole below.
        line_start = text.rfind("\n", 0, token.start) + 1
        if text[line_start:token.start].strip():
            continue
        match = re.match(r"--(?: omastart:off)?\s*(o\.(?:launch_on_start|exec_on_start)\s*\(.*)$", token.text)
        if not match:
            continue
        parsed = parse(match[1])
        if len(parsed) == 1 and not parsed[0]["readOnly"]:
            value = parsed[0]
            value.update(start=line_start, end=token.end,
                         fragment=text[line_start:token.end], enabled=False,
                         uncomment=text[line_start:token.start] + match[1],
                         line=text.count("\n", 0, token.start) + 1)
            results.append(value)
    # Consecutive managed comment lines represent one complete original call.
    lines = text.splitlines(keepends=True)
    managed_positions = {t.start for t in tokens if t.kind == "comment" and t.depth == 0
                         and t.text.startswith("-- omastart:off ")}
    offset = 0
    block = []
    block_start = 0
    block_end = 0

    def flush():
        if not block:
            return
        uncomment = "".join(block)
        parsed = parse(uncomment)
        if len(parsed) == 1 and not parsed[0]["readOnly"]:
            value = parsed[0]
            value.update(start=block_start, end=block_end, fragment=text[block_start:block_end],
                         uncomment=uncomment, enabled=False, line=text.count("\n", 0, block_start) + 1)
            results.append(value)
        else:
            results.append(dict(start=block_start, end=block_end, fragment=text[block_start:block_end],
                                command=uncomment.strip(), enabled=False,
                                readOnly="This disabled block contains multiple or unsupported statements.",
                                line=text.count("\n", 0, block_start) + 1))

    for line in lines:
        match = re.match(r"^([ \t]*)-- omastart:off (.*)", line, re.S)
        if match and offset + len(match[1]) in managed_positions:
            if not block:
                block_start = offset
            block.append(match[1] + match[2])
            block_end = offset + len(line)
            completed = parse("".join(block))
            if len(completed) == 1 and not completed[0]["readOnly"]:
                flush()
                block = []
        else:
            flush()
            block = []
        offset += len(line)
    flush()
    return sorted(results, key=lambda row: row["start"])


def discover(roots, store, catalog, warnings):
    if not roots.lua.exists():
        return []
    try:
        text = read_text(roots.lua)
    except Error as exc:
        return [source("hyprland", "unreadable", "Hyprland autostart", "", roots.lua, None,
                       readOnly=str(exc), eligible=None)]
    revision = digest(snapshot(roots.lua))
    rows = []
    for index, entry in enumerate(parse(text)):
        app_id = identity(entry["command"])
        key = digest([entry["command"], index])[:20]
        item = source("hyprland", key, app_id or f"Startup statement · line {entry['line']}",
                      entry["command"], roots.lua, entry["enabled"], line=entry["line"],
                      readOnly=entry["readOnly"] or store.writable(roots.lua), revision=revision,
                      _entry=entry, _text=text)
        enrich(item, catalog)
        if entry["fragment"].strip() == '-- o.launch_on_start("my-service")':
            item.update(system=True, readOnly="Commented Omarchy template example; this is not an installed application.")
        rows.append(item)
    return rows


def toggle(item, enabled, roots, store, runner):
    entry = item["_entry"]
    text = item["_text"]
    fragment = entry["fragment"]
    if enabled:
        replacement = entry["uncomment"]
    else:
        # Comment every line of a multiline literal call. Such a disabled
        # block is restored from the journal (not interpreted as Lua).
        replacement = "\n".join(re.sub(r"^(\s*)", r"\1-- omastart:off ", line, count=1)
                                for line in fragment.split("\n"))
    candidate = text[:entry["start"]] + replacement + text[entry["end"]:]
    runner(["luac", "-p", "-"], input=candidate)
    before = snapshot(roots.lua)
    if digest(before) != item["revision"]:
        raise Error("The autostart file changed. Refresh and try again.")
    return store.transact(item["id"], [(roots.lua, before, file_value(candidate.encode(), before.get("mode", 0o644)))])
