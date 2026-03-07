import os

templates_dir = 'templates'
old_logo = '<h2 class="text-xl font-black text-primary italic">Melo <span\n                    class="text-slate-900 dark:text-white not-italic">Finance</span></h2>'
new_logo = '''<h2 class="text-xl font-black text-primary italic">Melo <span
                    class="text-slate-900 dark:text-white not-italic">Finance</span></h2>
            <span class="bg-primary text-white text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-tighter">BETA</span>'''

for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'): continue
    path = os.path.join(templates_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'BETA' not in content and old_logo in content:
        print(f"Adding BETA badge to {filename}")
        modified = content.replace(old_logo, new_logo)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(modified)

print("Badge update done.")
