import json
from pathlib import Path

# Find project root by looking for 'app.py' in parent folders
current_dir = Path(__file__).resolve().parent
root_dir = current_dir

while root_dir != root_dir.parent:
    if (root_dir / "app.py").exists():
        break
    root_dir = root_dir.parent

print(f"Project root detected at: {root_dir}")

# Search for application_rates*.md recursively anywhere in the project
md_matches = list(root_dir.glob("**/application_rates*.md"))

if not md_matches:
    print(f"Error: No 'application_rates*.md' files found anywhere inside: {root_dir}")
else:
    md_file = md_matches[0]
    print(f"Found Markdown file: {md_file}")

    # Ensure target output path is always <project_root>/data/application_rates.json
    output_dir = root_dir / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_file = output_dir / "application_rates.json"

    # Read and convert
    md_content = md_file.read_text(encoding="utf-8")
    payload = {
        "full_page_content": md_content,
        "markdown": md_content,
        "source": md_file.name
    }

    json_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Successfully generated -> '{json_file}'")
