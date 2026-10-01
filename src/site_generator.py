import os
import datetime

def gerar_site_cliente(dados_cliente):
    nome_empresa = dados_cliente.get("nome_empresa", "Clínica Boutique")
    slug_pasta = dados_cliente.get("slug_pasta", "clinica-boutique")
    slogan = dados_cliente.get("slogan", "A precisão da odontologia. A arte do seu sorriso.")
    subtitulo = dados_cliente.get("subtitulo", "Atendimento exclusivo e humanizado.")
    cidade = dados_cliente.get("cidade", "Sua Cidade")
    telefone = dados_cliente.get("telefone", "(11) 99999-9999")
    whatsapp = dados_cliente.get("whatsapp", "5511999999999")
    ano_atual = datetime.datetime.now().year
    
    imagem_hero = "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?auto=format&fit=crop&w=1200&q=80"
    slogan_html = slogan.replace('. ', '.<br>') if '. ' in slogan else slogan

    html_content = f"""<!DOCTYPE html>
<html lang="pt-PT" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{nome_empresa} | Excelência em {cidade}</title>
    <meta name="description" content="{slogan} - {cidade}">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;500&family=Playfair+Display:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #FBFBF9;
            --text-color: #1A1A18;
            --accent-color: #5C6B56;
        }}
        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: 'DM Sans', sans-serif;
            -webkit-font-smoothing: antialiased;
            overflow-x: hidden;
        }}
        h1, h2, h3, .font-serif {{
            font-family: 'Playfair Display', serif;
        }}
        
        .bg-noise {{
            background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.03'/%3E%3C/svg%3E");
            pointer-events: none;
        }}

        .img-wrapper {{ overflow: hidden; }}
        .img-wrapper img {{ transition: transform 1.5s cubic-bezier(0.16, 1, 0.3, 1); }}
        .img-wrapper:hover img {{ transform: scale(1.05); }}

        .btn-premium {{
            background-color: var(--accent-color);
            color: #FFF;
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
        }}
        .btn-premium::after {{
            content: ''; position: absolute; top: 0; left: -100%; width: 100%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            transition: left 0.6s ease;
        }}
        .btn-premium:hover::after {{ left: 100%; }}
        .btn-premium:hover {{
            background-color: #4A5645; transform: translateY(-2px);
            box-shadow: 0 10px 30px -10px rgba(92, 107, 86, 0.5);
        }}

        .reveal {{
            opacity: 0; transform: translateY(30px);
            transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .reveal.active {{ opacity: 1; transform: translateY(0); }}
        .delay-100 {{ transition-delay: 100ms; }}
        .delay-200 {{ transition-delay: 200ms; }}
        .delay-300 {{ transition-delay: 300ms; }}
    </style>
</head>
<body class="relative selection:bg-[#5C6B56] selection:text-white">

    <div class="fixed inset-0 bg-noise z-0"></div>
    <div class="absolute top-0 left-0 w-[800px] h-[800px] bg-[#EBEBE5] rounded-full blur-[120px] -translate-x-1/2 -translate-y-1/2 z-0 opacity-50"></div>

    <div class="relative z-10">
        <!-- NAV -->
        <nav class="py-8 px-6 md:px-12 flex justify-between items-center reveal active">
            <div class="text-2xl font-serif tracking-tight">{nome_empresa}</div>
            <div class="hidden md:flex gap-10 text-xs uppercase tracking-widest text-gray-500">
                <a href="#a-clinica" class="hover:text-[#1A1A18] transition-colors relative group">
                    A Clínica
                    <span class="absolute -bottom-2 left-0 w-0 h-[1px] bg-[#1A1A18] transition-all group-hover:w-full"></span>
                </a>
                <a href="#especialidades" class="hover:text-[#1A1A18] transition-colors relative group">
                    Especialidades
                    <span class="absolute -bottom-2 left-0 w-0 h-[1px] bg-[#1A1A18] transition-all group-hover:w-full"></span>
                </a>
            </div>
            <a href="https://wa.me/{whatsapp}" target="_blank" class="text-xs uppercase tracking-widest font-medium border-b border-[#1A1A18] pb-1 hover:text-gray-500 hover:border-gray-500 transition-all">
                Agendar Consulta
            </a>
        </nav>

        <!-- HERO -->
        <section class="grid grid-cols-1 md:grid-cols-12 min-h-[85vh] relative pt-10 md:pt-0">
            <div class="md:col-span-6 flex flex-col justify-center px-6 md:px-16 lg:px-24 pb-16 md:pb-0 relative z-10">
                <h1 class="text-5xl md:text-7xl lg:text-[5.5rem] font-serif leading-[1.05] tracking-tight mb-8 reveal active delay-100">
                    {slogan_html}
                </h1>
                <p class="text-lg text-gray-600 max-w-md mb-12 leading-relaxed reveal active delay-200">
                    {subtitulo} Desenvolvemos sorrisos com precisão técnica e curadoria estética em {cidade}.
                </p>
                <div class="reveal active delay-300">
                    <a href="https://wa.me/{whatsapp}" target="_blank" class="btn-premium inline-flex items-center justify-center px-8 py-5 text-xs uppercase tracking-widest font-medium group">
                        Falar com Atendimento
                        <svg class="w-4 h-4 ml-3 transform transition-transform group-hover:translate-x-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="square" stroke-linejoin="miter" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
                    </a>
                </div>
            </div>
            
            <div class="md:col-span-6 relative h-[60vh] md:h-auto px-6 md:px-0 md:pr-12 md:py-12 reveal active delay-200">
                <div class="w-full h-full relative img-wrapper bg-gray-200 shadow-2xl shadow-gray-200/50">
                    <img src="{imagem_hero}" alt="Consultório" class="absolute inset-0 w-full h-full object-cover">
                </div>
                <div class="absolute bottom-4 left-0 md:-left-12 bg-white p-6 shadow-xl text-center reveal active delay-300">
                    <div class="font-serif text-3xl text-[#5C6B56] mb-1">+10</div>
                    <div class="text-[0.65rem] uppercase tracking-widest text-gray-400">Anos de<br>Tradição</div>
                </div>
            </div>
        </section>

        <!-- STATEMENT -->
        <section class="py-32 px-6">
            <div class="max-w-4xl mx-auto text-center reveal">
                <p class="text-3xl md:text-5xl font-serif italic text-gray-300 mb-8">"</p>
                <h2 class="text-3xl md:text-5xl font-serif leading-snug mb-12 text-[#1A1A18]">
                    Acreditamos que a saúde oral começa com a confiança. O nosso compromisso é aliar a tecnologia de ponta ao conforto humano, criando resultados que mudam vidas.
                </h2>
                <div class="text-xs uppercase tracking-widest text-gray-500">Direção Clínica — {nome_empresa}</div>
            </div>
        </section>

        <!-- ESPECIALIDADES -->
        <section id="especialidades" class="py-24 px-6 md:px-12 bg-white relative">
            <div class="max-w-6xl mx-auto reveal">
                <div class="text-xs uppercase tracking-widest text-gray-500 mb-16">Nossas Disciplinas</div>
                <div class="border-t border-gray-200">
                    <div class="group flex flex-col md:flex-row items-baseline py-12 border-b border-gray-200 hover:pl-6 transition-all duration-500 cursor-pointer">
                        <div class="text-sm text-gray-300 md:w-24 mb-4 md:mb-0 font-serif italic group-hover:text-[#5C6B56] transition-colors">01</div>
                        <h3 class="text-4xl md:text-5xl font-serif md:w-1/2 mb-4 md:mb-0 text-[#1A1A18]">Estética Dental</h3>
                        <p class="text-gray-500 md:w-1/3 leading-relaxed">Facetas e clareamento de alta precisão para redesenhar a harmonia do seu sorriso com naturalidade.</p>
                    </div>
                    <div class="group flex flex-col md:flex-row items-baseline py-12 border-b border-gray-200 hover:pl-6 transition-all duration-500 cursor-pointer">
                        <div class="text-sm text-gray-300 md:w-24 mb-4 md:mb-0 font-serif italic group-hover:text-[#5C6B56] transition-colors">02</div>
                        <h3 class="text-4xl md:text-5xl font-serif md:w-1/2 mb-4 md:mb-0 text-[#1A1A18]">Implantologia</h3>
                        <p class="text-gray-500 md:w-1/3 leading-relaxed">Recuperação funcional com tecnologia guiada e materiais biocompatíveis de última geração.</p>
                    </div>
                    <div class="group flex flex-col md:flex-row items-baseline py-12 border-b border-gray-200 hover:pl-6 transition-all duration-500 cursor-pointer">
                        <div class="text-sm text-gray-300 md:w-24 mb-4 md:mb-0 font-serif italic group-hover:text-[#5C6B56] transition-colors">03</div>
                        <h3 class="text-4xl md:text-5xl font-serif md:w-1/2 mb-4 md:mb-0 text-[#1A1A18]">Profilaxia</h3>
                        <p class="text-gray-500 md:w-1/3 leading-relaxed">Check-ups detalhados e prevenção ativa para manter a longevidade dos seus dentes naturais.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- FOOTER EDITORIAL (Sem classe reveal para garantir visibilidade) -->
        <footer class="bg-[#1A1A18] text-[#FBFBF9] py-24 px-6 md:px-12 border-t border-[#2A2A28]">
            <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-8">
                
                <!-- Coluna 1: Marca -->
                <div class="flex flex-col justify-between">
                    <div class="text-4xl font-serif tracking-tight mb-4">{nome_empresa}</div>
                    <p class="text-gray-400 text-sm max-w-xs leading-relaxed">
                        A arte do seu sorriso elevada ao mais alto padrão de excelência e conforto.
                    </p>
                </div>
                
                <!-- Coluna 2: Contacto -->
                <div class="flex flex-col md:items-center">
                    <div class="w-full md:w-auto">
                        <h4 class="text-[0.65rem] uppercase tracking-widest text-gray-500 mb-6">Contacto Directo</h4>
                        <a href="https://wa.me/{whatsapp}" class="text-2xl font-serif hover:text-[#5C6B56] transition-colors block mb-2">{telefone}</a>
                        <p class="text-gray-400 text-sm">Atendimento exclusivo em {cidade}</p>
                    </div>
                </div>
                
                <!-- Coluna 3: Links -->
                <div class="flex flex-col md:items-end">
                    <div class="w-full md:w-auto text-left md:text-right">
                        <h4 class="text-[0.65rem] uppercase tracking-widest text-gray-500 mb-6">Navegação</h4>
                        <a href="#a-clinica" class="block text-sm text-gray-400 hover:text-white transition-colors mb-3">A Clínica</a>
                        <a href="#especialidades" class="block text-sm text-gray-400 hover:text-white transition-colors">Especialidades</a>
                    </div>
                </div>
            </div>
            
            <!-- Direitos de Autor e Créditos -->
            <div class="max-w-6xl mx-auto mt-24 pt-8 border-t border-[#2A2A28] flex flex-col md:flex-row justify-between items-center text-xs text-gray-500">
                <p>&copy; {ano_atual} {nome_empresa}. Todos os direitos reservados.</p>
                <p class="mt-4 md:mt-0 uppercase tracking-widest">Web Design Premium</p>
            </div>
        </footer>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const reveals = document.querySelectorAll('.reveal');
            const revealOnScroll = () => {{
                for (let i = 0; i < reveals.length; i++) {{
                    const windowHeight = window.innerHeight;
                    const elementTop = reveals[i].getBoundingClientRect().top;
                    const elementVisible = 50;
                    if (elementTop < windowHeight - elementVisible) {{
                        reveals[i].classList.add('active');
                    }}
                }}
            }};
            window.addEventListener('scroll', revealOnScroll);
            revealOnScroll();
        }});
    </script>
</body>
</html>"""

    base_dir = "clientes_gerados"
    pasta_cliente = os.path.join(base_dir, slug_pasta)
    os.makedirs(pasta_cliente, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_cliente, "index.html")
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"✅ Obra-prima editorial forjada (com footer visível!): {caminho_arquivo}")