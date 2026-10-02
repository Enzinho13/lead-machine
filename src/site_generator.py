import os
import json

def render_component(component_def, theme):
    comp_type = component_def.get('type')
    props = component_def.get('props', {})
    
    components = {
        'HeroMinimalist': HeroMinimalist,
        'HeroEditorial': HeroEditorial,
        'HeroSplit': HeroSplit,
        'GridServices': GridServices,
        'ListServices': ListServices,
        'FeatureServices': FeatureServices,
        'AboutEditorial': AboutEditorial,
        'FooterMinimal': FooterMinimal,
        'FooterStandard': FooterStandard
    }
    
    if comp_type in components:
        return components[comp_type](props, theme)
    return f"<!-- Component {comp_type} not found -->"

def HeroMinimalist(props, theme):
    title = props.get('title', 'Title')
    subtitle = props.get('subtitle', '')
    return f"""
    <section class="min-h-[70vh] flex flex-col justify-center items-center text-center p-8 border-b border-black">
        <h1 class="text-6xl md:text-8xl font-medium tracking-tight mb-6 uppercase" style="font-family: {theme.get('font_heading', 'serif')};">{title}</h1>
        <p class="text-xl max-w-2xl text-gray-800" style="font-family: {theme.get('font_body', 'sans-serif')};">{subtitle}</p>
    </section>
    """

def HeroEditorial(props, theme):
    title = props.get('title', 'Title')
    subtitle = props.get('subtitle', '')
    return f"""
    <section class="py-24 px-8 md:px-16 border-b border-black">
        <div class="max-w-6xl mx-auto">
            <h1 class="text-6xl md:text-8xl font-medium tracking-tighter leading-none mb-8" style="font-family: {theme.get('font_heading', 'serif')};">{title}</h1>
            <p class="text-2xl md:text-3xl max-w-3xl leading-relaxed text-gray-900" style="font-family: {theme.get('font_body', 'sans-serif')};">{subtitle}</p>
        </div>
    </section>
    """

def HeroSplit(props, theme):
    title = props.get('title', 'Title')
    subtitle = props.get('subtitle', '')
    image_url = props.get('image_url', 'https://via.placeholder.com/800x600')
    return f"""
    <section class="grid grid-cols-1 md:grid-cols-2 min-h-screen border-b border-black">
        <div class="flex flex-col justify-center p-12 md:p-24 border-b md:border-b-0 md:border-r border-black">
            <h1 class="text-5xl md:text-7xl font-semibold mb-8 tracking-tighter" style="font-family: {theme.get('font_heading', 'serif')};">{title}</h1>
            <p class="text-lg md:text-xl text-gray-700" style="font-family: {theme.get('font_body', 'sans-serif')};">{subtitle}</p>
        </div>
        <div class="bg-gray-100 flex items-center justify-center p-8">
            <img src="{image_url}" alt="Hero Image" class="w-full object-cover shadow-none border border-black grayscale contrast-125" />
        </div>
    </section>
    """

def GridServices(props, theme):
    services = props.get('services', [])
    items_html = ""
    for s in services:
        items_html += f"""
        <div class="p-8 border border-black flex flex-col justify-between">
            <h3 class="text-2xl font-medium mb-4" style="font-family: {theme.get('font_heading', 'serif')};">{s.get('name', '')}</h3>
            <p class="text-gray-700 leading-relaxed text-sm uppercase tracking-wide" style="font-family: {theme.get('font_body', 'sans-serif')};">{s.get('description', '')}</p>
        </div>
        """
    return f"""
    <section class="py-24 px-8 border-b border-black">
        <div class="max-w-7xl mx-auto">
            <h2 class="text-4xl md:text-5xl mb-12 font-medium tracking-tight" style="font-family: {theme.get('font_heading', 'serif')};">Our Services</h2>
            <div class="grid grid-cols-1 md:grid-cols-3 gap-0 bg-black gap-[1px] border border-black">
                <div class="contents bg-white">{items_html}</div>
            </div>
        </div>
    </section>
    """

def ListServices(props, theme):
    services = props.get('services', [])
    items_html = ""
    for s in services:
        items_html += f"""
        <div class="py-8 border-b border-black last:border-b-0 flex flex-col md:flex-row md:items-baseline md:justify-between">
            <h3 class="text-3xl md:text-4xl font-medium md:w-1/3" style="font-family: {theme.get('font_heading', 'serif')};">{s.get('name', '')}</h3>
            <p class="text-lg text-gray-800 md:w-2/3 md:pl-12 mt-4 md:mt-0" style="font-family: {theme.get('font_body', 'sans-serif')};">{s.get('description', '')}</p>
        </div>
        """
    return f"""
    <section class="py-24 px-8 border-b border-black">
        <div class="max-w-5xl mx-auto">
            <h2 class="text-xs font-bold uppercase tracking-widest mb-16" style="font-family: {theme.get('font_body', 'sans-serif')};">Capabilities</h2>
            <div class="border-t border-black">
                {items_html}
            </div>
        </div>
    </section>
    """

def FeatureServices(props, theme):
    services = props.get('services', [])
    items_html = ""
    for i, s in enumerate(services):
        reverse_class = "md:flex-row-reverse" if i % 2 != 0 else ""
        img_border = "border-l" if i % 2 != 0 else "border-r"
        items_html += f"""
        <div class="flex flex-col md:flex-row border-b border-black last:border-b-0 {reverse_class}">
            <div class="md:w-1/2 border-b md:border-b-0 {img_border} border-black p-12 flex flex-col justify-center">
                <h3 class="text-4xl md:text-5xl font-medium mb-6" style="font-family: {theme.get('font_heading', 'serif')};">{s.get('name', '')}</h3>
                <p class="text-lg text-gray-700 leading-relaxed" style="font-family: {theme.get('font_body', 'sans-serif')};">{s.get('description', '')}</p>
            </div>
            <div class="md:w-1/2 bg-gray-50 flex items-center justify-center p-8">
                <img src="{s.get('image_url', 'https://via.placeholder.com/600x400')}" class="w-full h-auto border border-black grayscale" />
            </div>
        </div>
        """
    return f"""
    <section class="border-b border-black">
        {items_html}
    </section>
    """

def AboutEditorial(props, theme):
    text = props.get('text', 'About text')
    headline = props.get('headline', 'The Story')
    return f"""
    <section class="py-32 px-8 border-b border-black">
        <div class="max-w-4xl mx-auto">
            <h2 class="text-sm font-bold uppercase tracking-widest mb-12" style="font-family: {theme.get('font_body', 'sans-serif')};">{headline}</h2>
            <div class="text-3xl md:text-4xl leading-tight font-medium text-gray-900" style="font-family: {theme.get('font_heading', 'serif')};">
                {text}
            </div>
        </div>
    </section>
    """

def FooterMinimal(props, theme):
    text = props.get('text', '© 2024')
    return f"""
    <footer class="py-12 px-8 flex justify-between items-center text-sm uppercase tracking-widest bg-black text-white" style="font-family: {theme.get('font_body', 'sans-serif')};">
        <div>{text}</div>
        <div>All Rights Reserved</div>
    </footer>
    """

def FooterStandard(props, theme):
    company = props.get('company_name', 'Company')
    contact = props.get('contact', 'contact@example.com')
    return f"""
    <footer class="py-16 px-8 border-t border-black bg-white">
        <div class="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-start md:items-end">
            <div class="mb-8 md:mb-0">
                <h2 class="text-3xl font-medium mb-4" style="font-family: {theme.get('font_heading', 'serif')};">{company}</h2>
                <a href="mailto:{contact}" class="text-lg underline underline-offset-4 hover:bg-black hover:text-white transition-colors" style="font-family: {theme.get('font_body', 'sans-serif')};">{contact}</a>
            </div>
            <div class="text-sm uppercase tracking-widest text-gray-500" style="font-family: {theme.get('font_body', 'sans-serif')};">
                © {company}.
            </div>
        </div>
    </footer>
    """

def gerar_site_cliente(dados_site):
    slug = dados_site.get('slug', 'default-site')
    title = dados_site.get('title', 'Website')
    layout = dados_site.get('layout', [])
    theme = dados_site.get('theme', {'font_heading': 'serif', 'font_body': 'sans-serif', 'primary_color': '#000000'})
    
    font_imports = ""
    # Add some default Google Fonts if they are typical ones
    if theme.get('font_heading') == 'Playfair Display' or theme.get('font_body') == 'Inter':
        font_imports = "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Playfair+Display:ital,wght@0,400;0,600;1,400&display=swap' rel='stylesheet'>"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{
            color: #000;
            background-color: #fff;
            margin: 0;
            padding: 0;
            overflow-x: hidden;
            -webkit-font-smoothing: antialiased;
        }}
    </style>
    {font_imports}
</head>
<body class="border-x border-black max-w-[1600px] mx-auto min-h-screen shadow-2xl">
"""

    for component_def in layout:
        html_content += render_component(component_def, theme)

    html_content += """
</body>
</html>"""

    # Output paths
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'clientes_gerados', slug)
    os.makedirs(output_dir, exist_ok=True)
    
    index_path = os.path.join(output_dir, 'index.html')
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    vercel_path = os.path.join(output_dir, 'vercel.json')
    vercel_config = {
        "version": 2,
        "name": slug,
        "public": True
    }
    with open(vercel_path, 'w', encoding='utf-8') as f:
        json.dump(vercel_config, f, indent=2)
        
    return index_path