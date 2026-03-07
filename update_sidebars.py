import os
import re

templates_dir = 'templates'

sidebar_link = """            <a href="/analytics"
                class="flex items-center gap-3 p-3 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                <span class="material-symbols-outlined">analytics</span> Reportes y Analíticas
            </a>"""

for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'): continue
    path = os.path.join(templates_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'href="/analytics"' not in content:
        # Looking for the block:
        # <a href="/history/movements" ... >...</a>
        # and we append the new link after it
        pattern = r'(<a\s+href="/history/movements".*?</a>)'
        
        # We need to make sure we don't accidentally match the wrong thing, so DOTALL is used carefully
        # Alternatively, we just look for "/history/movements" block line by line.
        modified = re.sub(pattern, r'\1\n' + sidebar_link, content, flags=re.DOTALL)
        
        if modified != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f"Updated {filename}")

print("Sidebars updated.")
