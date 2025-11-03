from pathlib import Path

# katalog startowy
start_dir = Path(".")

# lista dozwolonych rozszerzeń (małe litery, z kropką)
allowed_exts = [".py"]

blacklisted_files = ["printer.py", "tester.py"]


def is_hidden(path: Path) -> bool:
    """Zwraca True, jeśli plik lub którykolwiek z jego rodziców jest ukryty."""
    return any(part.startswith(".") for part in path.parts)


for path in start_dir.rglob("*"):
    if path.is_file() and path.suffix.lower() in allowed_exts and not is_hidden(
            path) and path.name not in blacklisted_files:
        print(f"// {path}")
        try:
            print(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Błąd podczas czytania pliku: {e}]")
