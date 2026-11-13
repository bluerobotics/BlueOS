from pathlib import Path
from typing import Optional

USERDATA = Path("/usr/blueos/userdata")
STYLES_DIR = USERDATA / "styles"
MODELS_DIR = USERDATA / "modeloverrides"
BRANDING_DIR = USERDATA / "branding"

THEME_FILE = STYLES_DIR / "theme_style.css"
THEME_CONFIG_FILE = STYLES_DIR / "theme_config.json"

LOGO_BASENAME = "logo"
VEHICLE_IMAGE_BASENAME = "vehicle_image"

ALLOWED_MODEL_EXTENSIONS = {".glb"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}


def ensure_dirs() -> None:
    for directory in (STYLES_DIR, MODELS_DIR, BRANDING_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def safe_join(base: Path, user_path: str) -> Path:
    base = base.resolve()
    candidate = (base / user_path).resolve()
    # Prevents path traversal: "../../etc/passwd" style attacks
    # https://www.youtube.com/watch?v=RfiQYRn7fBg
    candidate.relative_to(base)
    return candidate


def find_branding_file(basename: str) -> Optional[Path]:
    if not BRANDING_DIR.exists():
        return None
    for entry in BRANDING_DIR.iterdir():
        if entry.is_file() and entry.stem == basename:
            return entry
    return None


def remove_branding_file(basename: str) -> None:
    existing = find_branding_file(basename)
    if existing is not None:
        existing.unlink()
