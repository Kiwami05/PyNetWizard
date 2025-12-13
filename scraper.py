#!/usr/bin/env python
from pathlib import Path

# ================== KONFIGURACJA ==================

start_dir = Path(".")
allowed_exts = [".py"]
blacklisted_files = ["scraper.py"]

MAX_LINES = 3000  # <<< x linii na plik wynikowy
OUT_PREFIX = "out"
OUT_SUFFIX = ".txt"

# =================================================


def is_hidden(path: Path) -> bool:
    """Zwraca True, jeśli plik lub którykolwiek z jego rodziców jest ukryty."""
    return any(part.startswith(".") for part in path.parts)


def get_file_block(path: Path) -> list[str]:
    """
    Zwraca listę linii, które dany plik wnosi do outputu:
    - nagłówek // path
    - zawartość pliku
    """
    lines = [f"// {path}\n"]
    try:
        content = path.read_text(encoding="utf-8").splitlines(keepends=True)
        lines.extend(content)
    except Exception as e:
        lines.append(f"[Błąd podczas czytania pliku: {e}]\n")
    return lines


def write_block(
    block: list[str],
    out_index: int,
) -> None:
    out_path = Path(f"{OUT_PREFIX}{out_index}{OUT_SUFFIX}")
    with out_path.open("w", encoding="utf-8") as f:
        f.writelines(block)


current_lines: list[str] = []
current_line_count = 0
out_index = 1

for path in start_dir.rglob("*"):
    if (
        path.is_file()
        and path.suffix.lower() in allowed_exts
        and not is_hidden(path)
        and path.name not in blacklisted_files
    ):
        block = get_file_block(path)
        block_len = len(block)

        # jeśli blok nie mieści się w aktualnym pliku → zapisz go
        if current_line_count > 0 and current_line_count + block_len > MAX_LINES:
            write_block(current_lines, out_index)
            out_index += 1
            current_lines = []
            current_line_count = 0

        # dodaj blok (nawet jeśli sam przekracza MAX_LINES)
        current_lines.extend(block)
        current_line_count += block_len

# zapisz resztę
if current_lines:
    write_block(current_lines, out_index)
