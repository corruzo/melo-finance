import os
import re

templates_dir = 'templates'
script_tag = '    <script src="/static/darkMode.js"></script>\n</head>'
theme_css = '''
        /* Prevención de parpadeo de modo oscuro */
        :root {
            --bg-light: #f5f6f8;
            --bg-dark: #0f1623;
        }
    </style>'''

dark_toggle_btn = '''                <button type="button" onclick="toggleDarkMode()"
                    class="flex size-10 items-center justify-center rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 hover:text-primary transition-colors">
                    <span class="material-symbols-outlined dark:hidden">dark_mode</span>
                    <span class="material-symbols-outlined hidden dark:block">light_mode</span>
                </button>
'''
# We will find the pattern for the profile icon in the header (which is usually a size-10 item next to notifications)
profile_icon_pattern = r'(\s*<a href="/settings/profile"\s+class="flex size-10[^>]+>\s*<span class="material-symbols-outlined.*?>person</span>\s*</a>)'

for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'): continue
    path = os.path.join(templates_dir, filename)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Add script in head
    if 'darkMode.js' not in content and '</head>' in content:
        content = content.replace('</head>', script_tag)
        
    # 2. Add css vars
    if '--bg-dark' not in content and '</style>' in content:
        content = content.replace('</style>', theme_css)

    # 3. Add toggle button before profile link in header
    if 'toggleDarkMode()' not in content:
        # Search for profile button in top nav
        content = re.sub(profile_icon_pattern, dark_toggle_btn + r'\1', content)
        
        # If it's sign-up or login or pages without profile button, add it somewhere at the top
        if 'toggleDarkMode()' not in content and (filename == 'login.html' or filename == 'sign-up.html'):
            # Insert after opening body or an obvious header div
            body_pattern = r'(<body[^>]*>)'
            top_btn = f'<div class="absolute top-4 right-4 z-50">{dark_toggle_btn}</div>'
            content = re.sub(body_pattern, r'\1\n' + top_btn, content)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Dark mode script added to all templates.")
