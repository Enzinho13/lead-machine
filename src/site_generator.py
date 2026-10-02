import os

class DesignSystem:
    @staticmethod
    def hero(dados):
        return f"""
        <section class="relative w-full h-[80vh] flex items-center justify-center overflow-hidden">
            <div class="absolute inset-0 bg-black/60 z-10"></div>
            <img src="{dados.get('imagem_hero')}" class="absolute inset-0 w-full h-full object-cover z-0" alt="Background Contextual">
            <div class="relative z-20 text-center text-white px-4 max-w-5xl mx-auto">
                <h1 class="text-5xl md:text-7xl font-serif font-bold mb-6 tracking-tight">{dados.get('slogan')}</h1>
                <p class="text-xl md:text-2xl font-light mb-8 text-gray-200">{dados.get('subtitulo')}</p>
                <a href="https://wa.me/{dados.get('whatsapp')}" class="px-8 py-4 bg-[var(--primary)] text-white font-medium text-lg rounded hover:opacity-90 transition">Falar com a Equipe</a>
            </div>
        </section>
        """

    @staticmethod
    def services(dados):
        cards = "".join([f"""
            <div class="p-8 bg-white border border-gray-100 hover:shadow-xl transition-all duration-300 group">
                <h3 class="text-2xl font-serif font-bold mb-4 group-hover:text-[var(--primary)] transition-colors">{s['titulo']}</h3>
                <p class="text-gray-600 leading-relaxed">{s['desc']}</p>
            </div>
        """ for s in dados.get('servicos', [])])
        
        return f"""
        <section class="py-24 bg-[#FBFBF9] px-6">
            <div class="max-w-7xl mx-auto">
                <h2 class="text-4xl font-serif font-bold mb-16 text-center text-gray-900">Nossa Expertise</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-8">{cards}</div>
            </div>
        </section>
        """

    @staticmethod
    def footer(dados):
        return f"""
        <footer class="bg-gray-900 text-white py-16 px-6">
            <div class="max-w-7xl mx-auto text-center">
                <h2 class="text-3xl font-serif font-bold mb-4">{dados.get('nome_empresa')}</h2>
                <p class="text-gray-400 mb-8">{dados.get('cidade')} | Estrutura Premium</p>
                <div class="w-16 h-1 bg-[var(--primary)] mx-auto mb-8"></div>
                <p class="text-sm text-gray-600">&copy; 2026 Todos os direitos reservados.</p>
            </div>
        </footer>
        """

def gerar_site_cliente(dados_cliente):
    slug = dados_cliente.get('slug_pasta')
    path = f"clientes_gerados/{slug}"
    os.makedirs(path, exist_ok=True)
    
    ds = DesignSystem()
    
    html = f"""<!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{dados_cliente.get('nome_empresa')}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>:root {{ --primary: {dados_cliente.get('cor_primaria', '#111')}; }}</style>
    </head>
    <body class="antialiased text-gray-800 selection:bg-[var(--primary)] selection:text-white">
        <nav class="p-6 absolute w-full z-50 flex justify-between items-center border-b border-white/10">
            <div class="text-2xl font-serif font-bold text-white tracking-wide">{dados_cliente.get('nome_empresa')}</div>
        </nav>
        {ds.hero(dados_cliente)}
        {ds.services(dados_cliente)}
        {ds.footer(dados_cliente)}
    </body>
    </html>"""
    
    with open(f"{path}/index.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    with open(f"{path}/vercel.json", "w", encoding="utf-8") as f:
        f.write('{"version": 2, "builds": [{"src": "index.html", "use": "@vercel/static"}]}')