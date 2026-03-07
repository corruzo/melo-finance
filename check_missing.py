import os
templates_dir = 'templates'
for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'): continue
    path = os.path.join(templates_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'Movimientos' in content and '/reports' not in content:
        print(f"MISSING in {filename}")
