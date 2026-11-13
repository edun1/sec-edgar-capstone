"""Create deployable Functions ZIP using current shared Python source."""
from pathlib import Path
import zipfile
ROOT = Path(__file__).resolve().parents[2]
output = ROOT / "azure" / "function.zip"
with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in (ROOT / "azure" / "functions").glob("*"):
        if path.is_file():
            archive.write(path, path.name)
    for directory in ("src", "config"):
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                archive.write(path, path.relative_to(ROOT))
print(output)
