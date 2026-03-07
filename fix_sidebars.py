import os
import re

templates_dir = 'templates'

# We want to add the reports link after the 'Movimientos' link if it's missing
sidebar_link = """            <a href="/reports"
                class="flex items-center gap-3 p-3 rounded-xl text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
                <span class="material-symbols-outlined">analytics</span> Reportes y Analíticas
            </a>"""

for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'): continue
    
    # Skip files that definitely don't have a sidebar or already have it
    if filename in ['login.html', 'sign-up.html']: continue
    
    path = os.path.join(templates_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '/reports' not in content and '/history/movements' in content:
        print(f"Updating {filename}...")
        # Pattern to find the movements link block
        pattern = r'(<a\s+[^>]*?href="/history/movements"[^>]*?>.*?</a>)'
        
        modified = re.sub(pattern, r'\1\n' + sidebar_link, content, flags=re.DOTALL)
        
        if modified != content:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f"Successfully updated {filename}")
        else:
            print(f"Could not find exact pattern in {filename}")

print("Done.")
