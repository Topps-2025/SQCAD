"""Crop generated story sheets into independently cacheable web illustrations."""
from pathlib import Path

from PIL import Image

ART = Path(__file__).resolve().parent
ASSETS = ART.parent / "assets"


def main() -> None:
    for case in ("alex", "finance", "care", "atlas"):
        for kind, names in (("future", ("A1", "A2", "B1", "B2")),
                            ("evidence", ("resolve", "probe", "uncertain", "delay"))):
            stem = ART / "generated" / "branching-v3" / f"{case}-{kind}-sheet"
            source = stem.with_suffix(".webp")
            if not source.exists():
                source = stem.with_suffix(".png")
            if not source.exists():
                print(f"Pending: {case}/{kind}")
                continue
            with Image.open(source) as sheet:
                width, height = sheet.size
                for i, name in enumerate(names):
                    left, top = (i % 2) * width // 2, (i // 2) * height // 2
                    # Trim the narrow painted gutter, preserving each scene's center.
                    panel = sheet.crop((left + 5, top + 5, left + width // 2 - 5,
                                        top + height // 2 - 5)).convert("RGB")
                    panel.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    panel.save(ASSETS / f"{case}-{kind}-{name}.webp", "WEBP", quality=88)
            print(f"Prepared four panels: {case}/{kind}")


if __name__ == "__main__":
    main()
