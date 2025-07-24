import os
from collections import defaultdict

TARGETS = ['manage.py', 'rust_engine', 'python_app']
EXCLUDES = ['rust_engine/Cargo.lock']
OUTPUT_FILE = 'AGI_PROJECT_DOCUMENTATION.md'

def get_extension(file_path):
    return os.path.splitext(file_path)[1].lower() or '[no_ext]'

# Delete existing output file
if os.path.exists(OUTPUT_FILE):
    os.remove(OUTPUT_FILE)

with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_file:
    for target in TARGETS:
        out_file.write(f"\n\n# 📁 Folder: `{target}`\n")
        ext_group = defaultdict(list)

        if os.path.isfile(target):
            if target not in EXCLUDES:
                ext = get_extension(target)
                ext_group[ext].append(target)
        elif os.path.isdir(target):
            for root, _, files in os.walk(target):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path in EXCLUDES:
                        continue
                    ext = get_extension(full_path)
                    ext_group[ext].append(full_path)

        for ext in sorted(ext_group):
            out_file.write(f"\n## 🗂️ Extension: `{ext}`\n")
            for file in sorted(ext_group[ext]):
                out_file.write(f"\n---\n### 📄 FILE: `{file}`\n")
                out_file.write(f"📂 Path: `{os.path.dirname(file)}`\n---\n")
                try:
                    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                        out_file.write(f.read())
                except Exception as e:
                    out_file.write(f"[Error reading file: {e}]\n")

print(f"✅ Done: {OUTPUT_FILE} (excluding {', '.join(EXCLUDES)})")
