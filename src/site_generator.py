import os

def gerar_site_cliente(dados_cliente: dict):
    """
    Gera um site de altíssimo padrão, com animações fluidas, interatividade via JS,
    design orgânico e zero cara de automação.
    """
    nome_pasta = dados_cliente.get("slug_pasta", "novo-site")
    caminho_base = os.path.join("clientes_gerados", nome_pasta)
    
    print(f"🚀 Forjando obra-prima digital para: {dados_cliente['nome_empresa']}...")
    
    os.makedirs(caminho_base, exist_ok=True)
    os.makedirs(os.path.join(caminho_base, "assets"), exist_ok=True)
    
    # 1. HTML Orgânico com Estrutura de Alta Conversão
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{dados_cliente['meta_description']}">
    <title>{dados_cliente['titulo_seo']}</title>
    <link rel="stylesheet" href="style.css">
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- FontAwesome para ícones -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>

    <!-- BOTÃO FLUTUANTE DE WHATSAPP DINÂMICO -->
    <a href="https://api.whatsapp.com/send?phone={dados_cliente['whatsapp']}&text=Olá! Vim pelo site e gostaria de tirar dúvidas." target="_blank" class="floating-whatsapp" title="Fale conosco no WhatsApp">
        <i class="fa-brands fa-whatsapp"></i>
    </a>

    <!-- HEADER FLUIDO -->
    <header class="site-header" id="header">
        <div class="container nav-container">
            <div class="logo-box">
                <span class="logo-text">{dados_cliente['nome_empresa']}</span>
            </div>
            <nav class="nav-menu" id="navMenu">
                <a href="#sobre">A Clínica</a>
                <a href="#servicos">Especialidades</a>
                <a href="#diferenciais">Diferenciais</a>
                <a href="#depoimentos">Depoimentos</a>
                <a href="https://api.whatsapp.com/send?phone={dados_cliente['whatsapp']}&text=Olá! Quero agendar um horário." target="_blank" class="btn-cta-header">
                    Agendar Horário
                </a>
            </nav>
            <div class="menu-toggle" id="menuToggle">
                <i class="fa-solid fa-bars"></i>
            </div>
        </div>
    </header>

    <!-- HERO SECTION IMERSIVA COM EFEITO DE PROFUNDIDADE -->
    <section class="hero-section" style="background-image: linear-gradient(135deg, rgba(11, 15, 25, 0.94) 0%, rgba(15, 23, 42, 0.8) 100%), url('{dados_cliente['imagem_hero']}');">
        <div class="container hero-content-wrapper">
            <div class="hero-badge animate-up">
                <span class="pulse-dot"></span> Excelência e Cuidado Humanizado
            </div>
            <h1 class="animate-up delay-1">{dados_cliente['slogan']}</h1>
            <p class="animate-up delay-2">{dados_cliente['subtitulo']}</p>
            <div class="hero-actions animate-up delay-3">
                <a href="https://api.whatsapp.com/send?phone={dados_cliente['whatsapp']}&text=Olá! Gostaria de agendar uma avaliação." target="_blank" class="btn-main-whatsapp">
                    <i class="fa-brands fa-whatsapp"></i> Falar com Atendimento
                </a>
                <a href="#servicos" class="btn-secondary-link">Explorar Especialidades <i class="fa-solid fa-arrow-down-long"></i></a>
            </div>
            <div class="hero-metrics animate-up delay-4">
                <div class="metric-item">
                    <strong>+10 Anos</strong>
                    <span>de Tradição</span>
                </div>
                <div class="separator-line"></div>
                <div class="metric-item">
                    <strong>98%</strong>
                    <span>Aprovação de Clientes</span>
                </div>
                <div class="separator-line"></div>
                <div class="metric-item">
                    <strong>Atendimento</strong>
                    <span>Exclusivo e Ágil</span>
                </div>
            </div>
        </div>
    </section>

    <!-- SEÇÃO SOBRE / MANIFESTO DA CLÍNICA -->
    <section id="sobre" class="about-section">
        <div class="container about-grid">
            <div class="about-text-content">
                <span class="tag-section">Nossa Filosofia</span>
                <h2>Um novo conceito em atendimento, feito para você se sentir em casa.</h2>
                <p>Aqui você não é apenas mais um número. Entendemos que cada sorriso e cada história exigem atenção única. Unimos tecnologia de ponta a um olhar genuinamente humano para transformar sua experiência do começo ao fim.</p>
                <div class="features-list">
                    <div class="feat-row"><i class="fa-solid fa-check-circle"></i> Ambiente 100% esterilizado e confortável</div>
                    <div class="feat-row"><i class="fa-solid fa-check-circle"></i> Sem filas de espera prolongadas</div>
                    <div class="feat-row"><i class="fa-solid fa-check-circle"></i> Planos adaptados à sua realidade</div>
                </div>
            </div>
            <div class="about-card-floating">
                <div class="card-icon-box"><i class="fa-solid fa-shield-heart"></i></div>
                <h3>Compromisso com o seu bem-estar</h3>
                <p>Nossa equipe passa por atualizações constantes para garantir procedimentos modernos, seguros e indolores.</p>
                <div class="card-author">
                    <span>Equipe Técnica Responsável</span>
                </div>
            </div>
        </div>
    </section>

    <!-- SEÇÃO DE SERVIÇOS / ESPECIALIDADES COM CARDS INTERATIVOS -->
    <section id="servicos" class="services-section">
        <div class="container">
            <div class="section-title-center">
                <span class="tag-section">O Que Fazemos de Melhor</span>
                <h2>Especialidades em Destaque</h2>
                <p>Soluções completas planejadas para devolver sua confiança e qualidade de vida.</p>
            </div>
            <div class="services-grid">
"""

    for servico in dados_cliente.get("servicos", []):
        html_content += f"""
                <div class="service-card-interactive">
                    <div class="service-icon-top"><i class="fa-solid fa-tooth"></i></div>
                    <h3>{servico['titulo']}</h3>
                    <p>{servico['descricao']}</p>
                    <a href="https://api.whatsapp.com/send?phone={dados_cliente['whatsapp']}&text=Olá! Quero saber mais sobre {servico['titulo']}." target="_blank" class="service-link-btn">
                        Agendar este serviço <i class="fa-solid fa-arrow-right"></i>
                    </a>
                </div>
"""

    html_content += f"""
            </div>
        </div>
    </section>

    <!-- SEÇÃO DE DIFERENCIAIS EM GRID MODERNO -->
    <section id="diferenciais" class="differentials-section">
        <div class="container">
            <div class="section-title-center">
                <span class="tag-section">Por Que Confiar em Nós</span>
                <h2>O Padrão {dados_cliente['nome_empresa']}</h2>
            </div>
            <div class="diff-grid-organic">
                <div class="diff-card">
                    <div class="diff-number">01</div>
                    <h4>Diagnóstico Preciso</h4>
                    <p>Utilizamos tecnologia avançada para mapear exatamente o que você precisa, sem tratamentos desnecessários.</p>
                </div>
                <div class="diff-card">
                    <div class="diff-number">02</div>
                    <h4>Acolhimento Total</h4>
                    <p>Do primeiro contato no WhatsApp até o pós-atendimento, nossa equipe está sempre pronta para auxiliar.</p>
                </div>
                <div class="diff-card">
                    <div class="diff-number">03</div>
                    <h4>Localização Privilegiada</h4>
                    <p>Fácil acesso em {dados_cliente.get('endereco', 'na região').split('-')[0]}, com total comodidade para você.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- DEPOIMENTOS / PROVA SOCIAL REALISTA -->
    <section id="depoimentos" class="testimonials-section">
        <div class="container">
            <div class="section-title-center">
                <span class="tag-section">Histórias Reais</span>
                <h2 style="color: white;">O Que Nossos Pacientes Dizem</h2>
            </div>
            <div class="testimonials-grid">
                <div class="testimonial-card-dark">
                    <div class="stars-row"><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i></div>
                    <p>"Simplesmente espetacular. Profissionais humanos, atenciosos e um resultado que superou todas as minhas expectativas. Recomendo de olhos fechados!"</p>
                    <span class="author-name">— Beatriz Lima</span>
                </div>
                <div class="testimonial-card-dark">
                    <div class="stars-row"><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i><i class="fa-solid fa-star"></i></div>
                    <p>"Ambiente impecável, pontualidade no atendimento e muita clareza em todas as etapas. Finalmente encontrei uma clínica de confiança."</p>
                    <span class="author-name">— Lucas Fernandes</span>
                </div>
            </div>
        </div>
    </section>

    <!-- CHAMADA FINAL DE ALTA CONVERSÃO -->
    <section class="final-cta-wrapper">
        <div class="container">
            <div class="cta-box-organic">
                <h2>Pronto para cuidar do seu sorriso com quem entende?</h2>
                <p>Agende sua avaliação agora mesmo e dê o primeiro passo rumo à sua melhor versão.</p>
                <a href="https://api.whatsapp.com/send?phone={dados_cliente['whatsapp']}&text=Olá! Vim pelo site e quero agendar meu horário." target="_blank" class="btn-main-whatsapp large-btn">
                    <i class="fa-brands fa-whatsapp"></i> Iniciar Conversa no WhatsApp
                </a>
            </div>
        </div>
    </section>

    <!-- RODAPÉ CLEAN -->
    <footer class="footer-organic">
        <div class="container footer-grid-org">
            <div>
                <span class="footer-logo-text">{dados_cliente['nome_empresa']}</span>
                <p class="footer-sub">{dados_cliente['slogan']}</p>
            </div>
            <div>
                <h4>Central de Atendimento</h4>
                <p><i class="fa-solid fa-phone"></i> {dados_cliente['telefone']}</p>
                <p><i class="fa-solid fa-location-dot"></i> {dados_cliente['endereco']}</p>
            </div>
        </div>
        <div class="footer-bottom-bar">
            <div class="container flex-between">
                <p>&copy; 2026 {dados_cliente['nome_empresa']}. Todos os direitos reservados.</p>
                <p>Excelência e Qualidade.</p>
            </div>
        </div>
    </footer>

    <!-- SCRIPT DE INTERATIVIDADE -->
    <script src="script.js"></script>
</body>
</html>
"""

    # 2. CSS Orgânico, Fluido e Sofisticado
    css_content = f"""
:root {{
    --primary: {dados_cliente.get('cor_primaria', '#0284c7')};
    --primary-dark: #0369a1;
    --accent: #38bdf8;
    --dark: #0b0f19;
    --slate: #475569;
    --light-bg: #f8fafc;
    --border-color: #e2e8f0;
    --white: #ffffff;
    --radius: 16px;
    --shadow-soft: 0 20px 40px -15px rgba(0, 0, 0, 0.05);
    --transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}}

* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

html {{
    scroll-behavior: smooth;
    font-family: 'Plus Jakarta Sans', sans-serif;
    color: var(--slate);
    background-color: var(--white);
}}

body {{
    line-height: 1.7;
    font-size: 1rem;
    overflow-x: hidden;
}}

.container {{
    max-width: 1120px;
    margin: 0 auto;
    padding: 0 24px;
}}

.flex-between {{
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

/* BOTÃO WHATSAPP FLUTUANTE */
.floating-whatsapp {{
    position: fixed;
    bottom: 30px;
    right: 30px;
    background-color: #25d366;
    color: var(--white);
    width: 60px;
    height: 60px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    box-shadow: 0 10px 25px rgba(37, 211, 102, 0.4);
    z-index: 9999;
    transition: var(--transition);
    text-decoration: none;
}}

.floating-whatsapp:hover {{
    transform: scale(1.1) rotate(5deg);
}}

/* HEADER DINÂMICO */
.site-header {{
    background: rgba(255, 255, 255, 0.9);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border-color);
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    z-index: 1000;
    transition: var(--transition);
}}

.site-header.scrolled {{
    box-shadow: 0 10px 30px rgba(0,0,0,0.08);
    background: rgba(255, 255, 255, 0.98);
}}

.nav-container {{
    height: 80px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

.logo-text {{
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--dark);
    letter-spacing: -0.5px;
}}

.nav-menu {{
    display: flex;
    align-items: center;
    gap: 30px;
}}

.nav-menu a {{
    text-decoration: none;
    color: var(--slate);
    font-weight: 600;
    font-size: 0.95rem;
    transition: var(--transition);
}}

.nav-menu a:hover {{
    color: var(--primary);
}}

.btn-cta-header {{
    background-color: var(--primary) !important;
    color: var(--white) !important;
    padding: 10px 22px;
    border-radius: 8px;
    box-shadow: 0 4px 15px rgba(2, 132, 199, 0.25);
}}

.menu-toggle {{
    display: none;
    font-size: 1.5rem;
    cursor: pointer;
    color: var(--dark);
}}

/* HERO SECTION */
.hero-section {{
    min-height: 95vh;
    background-size: cover;
    background-position: center;
    display: flex;
    align-items: center;
    color: var(--white);
    padding: 140px 0 80px 0;
    position: relative;
}}

.hero-content-wrapper {{
    max-width: 800px;
    margin: 0 auto;
    text-align: center;
}}

.hero-badge {{
    display: inline-flex;
    align-items: center;
    gap: 10px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 8px 18px;
    border-radius: 50px;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 25px;
    backdrop-filter: blur(5px);
}}

.pulse-dot {{
    width: 8px;
    height: 8px;
    background-color: #22c55e;
    border-radius: 50%;
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
    animation: pulse 1.5s infinite;
}}

@keyframes pulse {{
    0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7); }}
    70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }}
    100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }}
}}

.hero-content-wrapper h1 {{
    font-size: 3.5rem;
    font-weight: 800;
    line-height: 1.15;
    margin-bottom: 20px;
    letter-spacing: -1.5px;
}}

.hero-content-wrapper p {{
    font-size: 1.15rem;
    color: #cbd5e1;
    margin-bottom: 40px;
}}

.hero-actions {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
    margin-bottom: 60px;
}}

.btn-main-whatsapp {{
    background-color: #25d366;
    color: var(--white);
    padding: 16px 34px;
    border-radius: var(--radius);
    text-decoration: none;
    font-weight: 700;
    font-size: 1.05rem;
    display: inline-flex;
    align-items: center;
    gap: 12px;
    box-shadow: 0 10px 30px rgba(37, 211, 102, 0.35);
    transition: var(--transition);
}}

.btn-main-whatsapp:hover {{
    transform: translateY(-3px);
    background-color: #22bf5b;
}}

.btn-secondary-link {{
    color: var(--white);
    text-decoration: none;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: var(--transition);
}}

.btn-secondary-link:hover {{
    color: var(--accent);
}}

.hero-metrics {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 30px;
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(255,255,255,0.08);
    padding: 20px 40px;
    border-radius: var(--radius);
    backdrop-filter: blur(10px);
}}

.metric-item strong {{
    display: block;
    font-size: 1.25rem;
    color: var(--white);
    font-weight: 800;
}}

.metric-item span {{
    font-size: 0.8rem;
    color: #94a3b8;
}}

.separator-line {{
    width: 1px;
    height: 30px;
    background-color: rgba(255,255,255,0.15);
}}

/* ABOUT SECTION */
.about-section {{
    padding: 120px 0;
    background-color: var(--light-bg);
}}

.about-grid {{
    display: grid;
    grid-template-columns: 1.2fr 0.8fr;
    gap: 60px;
    align-items: center;
}}

.tag-section {{
    color: var(--primary);
    font-weight: 700;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 2px;
    display: block;
    margin-bottom: 12px;
}}

.about-text-content h2 {{
    font-size: 2.5rem;
    font-weight: 800;
    color: var(--dark);
    margin-bottom: 20px;
    line-height: 1.2;
    letter-spacing: -0.5px;
}}

.features-list {{
    margin-top: 30px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}}

.feat-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-weight: 600;
    color: var(--dark);
}}

.feat-row i {{
    color: #22c55e;
    font-size: 1.1rem;
}}

.about-card-floating {{
    background: var(--white);
    padding: 45px;
    border-radius: var(--radius);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-soft);
    position: relative;
    transition: var(--transition);
}}

.about-card-floating:hover {{
    transform: translateY(-5px);
}}

.card-icon-box {{
    width: 60px;
    height: 60px;
    background: rgba(2, 132, 199, 0.08);
    color: var(--primary);
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    margin-bottom: 25px;
}}

.about-card-floating h3 {{
    font-size: 1.35rem;
    color: var(--dark);
    margin-bottom: 15px;
    font-weight: 700;
}}

.card-author {{
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid var(--border-color);
    font-size: 0.85rem;
    font-weight: 700;
    color: var(--primary);
}}

/* SERVICES SECTION */
.services-section {{
    padding: 120px 0;
}}

.section-title-center {{
    text-align: center;
    max-width: 650px;
    margin: 0 auto 70px auto;
}}

.section-title-center h2 {{
    font-size: 2.5rem;
    font-weight: 800;
    color: var(--dark);
    margin-top: 5px;
    margin-bottom: 15px;
    letter-spacing: -0.5px;
}}

.services-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 30px;
}}

.service-card-interactive {{
    background: var(--white);
    padding: 45px 35px;
    border-radius: var(--radius);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-soft);
    transition: var(--transition);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}}

.service-card-interactive:hover {{
    transform: translateY(-8px);
    border-color: var(--primary);
    box-shadow: 0 30px 50px -20px rgba(2, 132, 199, 0.15);
}}

.service-icon-top {{
    width: 60px;
    height: 60px;
    background: var(--light-bg);
    color: var(--primary);
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.5rem;
    margin-bottom: 25px;
    transition: var(--transition);
}}

.service-card-interactive:hover .service-icon-top {{
    background: var(--primary);
    color: var(--white);
}}

.service-card-interactive h3 {{
    font-size: 1.35rem;
    color: var(--dark);
    margin-bottom: 12px;
    font-weight: 700;
}}

.service-card-interactive p {{
    font-size: 0.95rem;
    margin-bottom: 30px;
}}

.service-link-btn {{
    color: var(--primary);
    text-decoration: none;
    font-weight: 700;
    font-size: 0.95rem;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: var(--transition);
}}

.service-link-btn:hover {{
    gap: 12px;
}}

/* DIFFERENTIALS */
.differentials-section {{
    padding: 120px 0;
    background-color: var(--light-bg);
}}

.diff-grid-organic {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 30px;
}}

.diff-card {{
    background: var(--white);
    padding: 45px;
    border-radius: var(--radius);
    border: 1px solid var(--border-color);
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-soft);
}}

.diff-number {{
    font-size: 3.5rem;
    font-weight: 900;
    color: rgba(2, 132, 199, 0.06);
    position: absolute;
    top: 20px;
    right: 25px;
}}

.diff-card h4 {{
    font-size: 1.3rem;
    color: var(--dark);
    margin-bottom: 12px;
    font-weight: 700;
}}

/* TESTIMONIALS */
.testimonials-section {{
    padding: 120px 0;
    background-color: var(--dark);
}}

.testimonials-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
    gap: 30px;
}}

.testimonial-card-dark {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 45px;
    border-radius: var(--radius);
    backdrop-filter: blur(10px);
}}

.stars-row {{
    color: #f59e0b;
    margin-bottom: 20px;
    font-size: 0.95rem;
}}

.testimonial-card-dark p {{
    font-style: italic;
    color: #e2e8f0;
    margin-bottom: 25px;
    font-size: 1.05rem;
}}

.author-name {{
    font-weight: 700;
    color: var(--accent);
    font-size: 0.95rem;
}}

/* FINAL CTA */
.final-cta-wrapper {{
    padding: 100px 0 120px 0;
    background-color: var(--light-bg);
}}

.cta-box-organic {{
    background: linear-gradient(135deg, var(--dark), #1e293b);
    color: var(--white);
    padding: 70px 50px;
    border-radius: 24px;
    text-align: center;
    box-shadow: 0 25px 50px rgba(0,0,0,0.15);
}}

.cta-box-organic h2 {{
    font-size: 2.6rem;
    font-weight: 800;
    margin-bottom: 15px;
    letter-spacing: -0.5px;
}}

.cta-box-organic p {{
    color: #94a3b8;
    max-width: 600px;
    margin: 0 auto 40px auto;
    font-size: 1.15rem;
}}

.large-btn {{
    padding: 18px 40px;
    font-size: 1.15rem;
}}

/* FOOTER */
.footer-organic {{
    background-color: #070a12;
    color: var(--white);
    padding: 80px 0 35px 0;
}}

.footer-grid-org {{
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 50px;
    margin-bottom: 60px;
}}

.footer-logo-text {{
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--white);
    display: block;
    margin-bottom: 15px;
}}

.footer-sub {{
    color: #94a3b8;
    max-width: 350px;
    font-size: 0.95rem;
}}

.footer-organic h4 {{
    font-size: 1.1rem;
    margin-bottom: 20px;
    color: var(--accent);
}}

.footer-organic p {{
    color: #94a3b8;
    font-size: 0.95rem;
    margin-bottom: 10px;
}}

.footer-bottom-bar {{
    border-top: 1px solid rgba(255,255,255,0.06);
    padding-top: 30px;
    color: #64748b;
    font-size: 0.85rem;
}}

/* ANIMAÇÕES DE ENTRADA */
.animate-up {{
    opacity: 0;
    transform: translateY(30px);
    animation: fadeInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}}

.delay-1 {{ animation-delay: 0.15s; }}
.delay-2 {{ animation-delay: 0.3s; }}
.delay-3 {{ animation-delay: 0.45s; }}
.delay-4 {{ animation-delay: 0.6s; }}

@keyframes fadeInUp {{
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

@media (max-width: 768px) {{
    .about-grid, .footer-grid-org {{
        grid-template-columns: 1fr;
    }}
    .hero-content-wrapper h1 {{
        font-size: 2.4rem;
    }}
    .nav-menu {{
        display: none;
        position: absolute;
        top: 80px;
        left: 0;
        width: 100%;
        background: var(--white);
        flex-direction: column;
        padding: 30px;
        border-bottom: 1px solid var(--border-color);
        box-shadow: 0 15px 30px rgba(0,0,0,0.1);
    }}
    .nav-menu.active {{
        display: flex;
    }}
    .menu-toggle {{
        display: block;
    }}
    .hero-metrics {{
        flex-direction: column;
        gap: 15px;
    }}
    .separator-line {{
        width: 100%;
        height: 1px;
    }}
}}
"""

    # 3. JavaScript Leve para Interatividade Real (Menu mobile e efeito de scroll no header)
    js_content = """
document.addEventListener("DOMContentLoaded", function() {
    // Efeito de sombra no Header ao rolar a página
    const header = document.getElementById("header");
    window.addEventListener("scroll", function() {
        if (window.scrollY > 40) {
            header.classList.add("scrolled");
        } else {
            header.classList.remove("scrolled");
        }
    });

    // Menu Mobile Toggle
    const menuToggle = document.getElementById("menuToggle");
    const navMenu = document.getElementById("navMenu");

    if (menuToggle) {
        menuToggle.addEventListener("click", function() {
            navMenu.classList.toggle("active");
        });
    }
});
"""

    # Salvando os arquivos fisicamente
    with open(os.path.join(caminho_base, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)
        
    with open(os.path.join(caminho_base, "style.css"), "w", encoding="utf-8") as f:
        f.write(css_content)

    with open(os.path.join(caminho_base, "script.js"), "w", encoding="utf-8") as f:
        f.write(js_content)
        
    print(f"✅ Obra-prima gerada com sucesso em: {caminho_base}/")

if __name__ == "__main__":
    briefing_exemplo = {
        "slug_pasta": "clinica-sorriso-perfeito",
        "nome_empresa": "Clínica Sorriso Perfeito",
        "titulo_seo": "Clínica Sorriso Perfeito | Implantes e Clareamento",
        "meta_description": "Procurando dentista especializado? Conheça a Clínica Sorriso Perfeito. Agende sua avaliação pelo WhatsApp.",
        "slogan": "Transformando o seu sorriso com excelência e tecnologia",
        "subtitulo": "Especialistas em estética dental, implantes e reabilitação oral com um atendimento humanizado que coloca você em primeiro lugar.",
        "whatsapp": "5511999999999",
        "telefone": "(11) 4002-8922",
        "endereco": "Rua das Flores, 123 - Centro, Bragança Paulista - SP",
        "cor_primaria": "#0284c7",
        "imagem_hero": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?auto=format&fit=crop&w=1600&q=85",
        "servicos": [
            {"titulo": "Clareamento a Laser", "descricao": "Tenha dentes visivelmente mais brancos em uma única sessão, com segurança total e sem sensibilidade."},
            {"titulo": "Implantes Dentários", "descricao": "Recupere a firmeza, a função mastigatória e a beleza do seu sorriso com técnicas modernas e indolores."},
            {"titulo": "Ortodontia Estética", "descricao": "Aparelhos discretos e alinhadores invisíveis projetados para corrigir seu sorriso com elegância."}
        ]
    }
    
    gerar_site_cliente(briefing_exemplo)