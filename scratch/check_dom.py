with open('main.py', 'r', encoding='utf-8') as f:
    html = f.read()
for id_name in ['lg-domain', 'lg-subdomain', 'lg-path', 'lg-template-select', 'lg-landing-template', 'lg-success-template', 'lg-landing-url', 'lg-deployments-tbody']:
    print(id_name, 'exists:', f'id="{id_name}"' in html or f"id='{id_name}'" in html)
