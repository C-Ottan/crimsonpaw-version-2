# ── landing.py ──────────────────────────────────────────────
# Crimson Paw Public Landing Page Template
# Fully authentic replica of the crystal red-team pentest suite design

CRIMSON_PAW_LANDING_HTML = r'''<!DOCTYPE html>
<html lang="en" data-theme="{{ active_theme or 'crimson' }}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ platform_name or 'CRIMSON PAW' }} — Crystal-Powered Pentest Suite</title>
    <link rel="icon" type="image/png" href="{{ custom_logo_url or '/static/img/crimson_paw_logo.png' }}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root, [data-theme="crimson"] { 
            --bg-primary: #0a0709; --bg-sidebar: #100b0e; --bg-panel: #161014; 
            --border-color: #2e1216; --border-hover: #4e1a22;
            --text-primary: #f0ebed; --text-secondary: #a49498; 
            --accent-color: #e50914; --accent-hover: #ff2a35;
            --accent-glow: rgba(229, 9, 20, 0.35); --accent-glow-strong: rgba(229, 9, 20, 0.65);
            --accent-gradient: linear-gradient(135deg, #e50914, #b00710);
            --accent-gradient-hover: linear-gradient(135deg, #ff1f2a, #cc0813);
            --badge-bg: #261115; --badge-border: #5a1c22; --badge-color: #ff8b94;
            --danger: #e50914; --success: #2ea043;
        }
        [data-theme="blue"] {
            --bg-primary: #050a14; --bg-sidebar: #091020; --bg-panel: #0d172e;
            --border-color: #16264c; --border-hover: #23407d;
            --text-primary: #e6f0ff; --text-secondary: #8da2c0;
            --accent-color: #0084ff; --accent-hover: #339cff;
            --accent-glow: rgba(0, 132, 255, 0.35); --accent-glow-strong: rgba(0, 132, 255, 0.65);
            --accent-gradient: linear-gradient(135deg, #0084ff, #0056b3);
            --accent-gradient-hover: linear-gradient(135deg, #339cff, #006ee6);
            --badge-bg: #0d2244; --badge-border: #1a427d; --badge-color: #80bfff;
            --danger: #e50914; --success: #2ea043;
        }
        [data-theme="green"] {
            --bg-primary: #051208; --bg-sidebar: #091c0e; --bg-panel: #0e2b16;
            --border-color: #154522; --border-hover: #1e6633;
            --text-primary: #e6ffed; --text-secondary: #8dc09a;
            --accent-color: #00e676; --accent-hover: #33eb91;
            --accent-glow: rgba(0, 230, 118, 0.35); --accent-glow-strong: rgba(0, 230, 118, 0.65);
            --accent-gradient: linear-gradient(135deg, #00c853, #009624);
            --accent-gradient-hover: linear-gradient(135deg, #00e676, #00b248);
            --badge-bg: #0b3318; --badge-border: #14592a; --badge-color: #69f0ae;
            --danger: #e50914; --success: #2ea043;
        }
        [data-theme="purple"] {
            --bg-primary: #0a0514; --bg-sidebar: #120924; --bg-panel: #1b0e36;
            --border-color: #311860; --border-hover: #4a2491;
            --text-primary: #f3e8ff; --text-secondary: #aa95c4;
            --accent-color: #a855f7; --accent-hover: #be7bf9;
            --accent-glow: rgba(168, 85, 247, 0.35); --accent-glow-strong: rgba(168, 85, 247, 0.65);
            --accent-gradient: linear-gradient(135deg, #9333ea, #6b21a8);
            --accent-gradient-hover: linear-gradient(135deg, #a855f7, #7e22ce);
            --badge-bg: #29144d; --badge-border: #4d238c; --badge-color: #d8b4fe;
            --danger: #e50914; --success: #2ea043;
        }
        [data-theme="amber"] {
            --bg-primary: #120c04; --bg-sidebar: #1c1307; --bg-panel: #291b0b;
            --border-color: #4a3114; --border-hover: #734c1f;
            --text-primary: #fff8e6; --text-secondary: #c4ad8d;
            --accent-color: #f59e0b; --accent-hover: #fbbf24;
            --accent-glow: rgba(245, 158, 11, 0.35); --accent-glow-strong: rgba(245, 158, 11, 0.65);
            --accent-gradient: linear-gradient(135deg, #d97706, #b45309);
            --accent-gradient-hover: linear-gradient(135deg, #f59e0b, #d97706);
            --badge-bg: #3d260f; --badge-border: #6b431a; --badge-color: #fcd34d;
            --danger: #e50914; --success: #2ea043;
        }
        [data-theme="titanium"] {
            --bg-primary: #0a0c10; --bg-sidebar: #11141a; --bg-panel: #191e26;
            --border-color: #28303d; --border-hover: #3d495c;
            --text-primary: #f1f5f9; --text-secondary: #94a3b8;
            --accent-color: #38bdf8; --accent-hover: #7dd3fc;
            --accent-glow: rgba(56, 189, 248, 0.35); --accent-glow-strong: rgba(56, 189, 248, 0.65);
            --accent-gradient: linear-gradient(135deg, #0284c7, #0369a1);
            --accent-gradient-hover: linear-gradient(135deg, #38bdf8, #0284c7);
            --badge-bg: #132338; --badge-border: #23426b; --badge-color: #7dd3fc;
            --danger: #e50914; --success: #2ea043;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-primary);
            background-image: 
                radial-gradient(circle at 50% 15%, var(--accent-glow) 0%, transparent 60%),
                radial-gradient(circle at 85% 60%, var(--accent-glow-strong) 0%, transparent 50%);
            background-position: center, center, 40px 0, 40px 0, 0 0, 0 0;
            background-size: 100% 100%, 100% 100%, 80px 80px, 80px 80px, 80px 80px, 80px 80px;
            color: #f0eaed;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* ── Header ── */
        header {
            width: 100%;
            height: 72px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 48px;
            background: var(--bg-sidebar);
            backdrop-filter: blur(14px);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .nav-brand {
            display: flex;
            align-items: center;
            gap: 14px;
            text-decoration: none;
        }
        .nav-brand-logo {
            width: 42px;
            height: 42px;
            border-radius: 10px;
            object-fit: cover;
            border: 1px solid var(--border-color);
            box-shadow: 0 0 14px var(--accent-glow);
        }
        .nav-brand-text {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .nav-brand-title {
            font-size: 15px;
            font-weight: 900;
            letter-spacing: 0.18em;
            color: #ffffff;
            text-transform: uppercase;
        }
        .nav-brand-sub {
            font-size: 9.5px;
            font-weight: 700;
            letter-spacing: 0.1em;
            color: #b09ba2;
            text-transform: uppercase;
        }
        .nav-links {
            display: flex;
            align-items: center;
            gap: 28px;
        }
        .nav-link {
            color: #e5dfe2;
            font-size: 13.5px;
            font-weight: 600;
            text-decoration: none;
            transition: color 0.15s;
            cursor: pointer;
        }
        .nav-link:hover {
            color: var(--accent-color);
        }
        .nav-btn-signin {
            background: var(--accent-gradient);
            color: #ffffff;
            padding: 8px 24px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 700;
            text-decoration: none;
            box-shadow: 0 0 18px var(--accent-glow);
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }
        .nav-btn-signin:hover {
            background: var(--accent-gradient-hover);
            box-shadow: 0 0 24px var(--accent-glow-strong);
            transform: translateY(-1px);
        }

        /* ── Main Hero Layout ── */
        main {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 50px 24px;
        }
        .hero-container {
            max-width: 1180px;
            width: 100%;
            display: grid;
            grid-template-columns: 1.35fr 0.85fr;
            gap: 36px;
            align-items: center;
        }

        /* Left Hero Card */
        .hero-card {
            background: var(--bg-panel);
            border: 1px solid var(--border-color);
            border-radius: 28px;
            padding: 44px 48px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.08);
            backdrop-filter: blur(16px);
            position: relative;
            overflow: hidden;
        }
        .hero-card::before {
            content: '';
            position: absolute;
            top: -120px;
            left: -120px;
            width: 260px;
            height: 260px;
            background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
            pointer-events: none;
        }
        .hero-tag {
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.2em;
            color: #c9a7af;
            text-transform: uppercase;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .hero-tag::before {
            content: '';
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--accent-color);
            box-shadow: 0 0 8px var(--accent-color);
        }
        .hero-title {
            font-size: 2.75rem;
            font-weight: 900;
            line-height: 1.15;
            letter-spacing: -0.02em;
            color: #ffffff;
            margin-bottom: 22px;
        }
        .hero-desc {
            font-size: 14.5px;
            color: #a4979e;
            line-height: 1.65;
            margin-bottom: 14px;
        }
        .hero-desc-sec {
            font-size: 14.5px;
            color: #a4979e;
            line-height: 1.65;
            margin-bottom: 32px;
        }
        .hero-cta-btn {
            background: var(--accent-gradient);
            color: #ffffff;
            padding: 13px 34px;
            border-radius: 9999px;
            font-size: 12.5px;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border: 1px solid rgba(255, 255, 255, 0.2);
            cursor: pointer;
            box-shadow: 0 6px 26px var(--accent-glow);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }
        .hero-cta-btn:hover {
            background: var(--accent-gradient-hover);
            box-shadow: 0 8px 32px var(--accent-glow-strong);
            transform: translateY(-2px);
        }

        /* Right Hero Column */
        .hero-right-col {
            display: flex;
            flex-direction: column;
            gap: 20px;
            align-items: center;
        }
        .logo-card {
            width: 100%;
            max-width: 360px;
            height: 380px;
            background: rgba(16, 10, 14, 0.85);
            border: 1px solid var(--border-color);
            border-radius: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.06);
            backdrop-filter: blur(16px);
            position: relative;
            overflow: hidden;
            transition: transform 0.3s ease, border-color 0.3s ease;
        }
        .logo-card:hover {
            transform: translateY(-4px);
            border-color: var(--accent-color);
        }
        .logo-card::after {
            content: '';
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 50% 50%, var(--accent-glow) 0%, transparent 70%);
            pointer-events: none;
        }
        .logo-card-img {
            width: 84%;
            height: 84%;
            object-fit: contain;
            filter: drop-shadow(0 0 30px var(--accent-glow));
            position: relative;
            z-index: 2;
        }

        /* Disclaimer Card */
        .disclaimer-card {
            width: 100%;
            max-width: 360px;
            background: rgba(18, 12, 16, 0.85);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 16px 20px;
            display: flex;
            align-items: flex-start;
            gap: 14px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            backdrop-filter: blur(12px);
        }
        .disclaimer-icon-wrap {
            width: 34px;
            height: 34px;
            border-radius: 9px;
            background: var(--badge-bg);
            border: 1px solid var(--badge-border);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            color: var(--accent-color);
            font-size: 15px;
        }
        .disclaimer-content {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }
        .disclaimer-label {
            font-size: 10.5px;
            font-weight: 800;
            letter-spacing: 0.14em;
            color: #c9a7af;
            text-transform: uppercase;
        }
        .disclaimer-text {
            font-size: 12px;
            color: #d8ced3;
            line-height: 1.45;
        }

        /* ── Pricing Modal ── */
        .modal-backdrop {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(5, 3, 5, 0.85);
            backdrop-filter: blur(10px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal-backdrop.open { display: flex; }
        .pricing-modal {
            background: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            max-width: 960px;
            width: 100%;
            padding: 36px 40px;
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.8), 0 0 40px var(--accent-glow);
            position: relative;
        }
        .modal-close {
            position: absolute;
            top: 20px;
            right: 24px;
            background: transparent;
            border: none;
            color: #a49498;
            font-size: 24px;
            cursor: pointer;
            transition: color 0.15s;
        }
        .modal-close:hover { color: #ffffff; }
        .pricing-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .pricing-header h2 {
            font-size: 1.85rem;
            font-weight: 900;
            color: #ffffff;
            margin-bottom: 6px;
        }
        .pricing-header p {
            font-size: 0.9rem;
            color: #a49498;
        }
        .pricing-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
        }
        .price-card {
            background: var(--bg-panel);
            border: 1px solid var(--border-color);
            border-radius: 18px;
            padding: 24px 22px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            position: relative;
            transition: border-color 0.2s, transform 0.2s;
        }
        .price-card:hover {
            border-color: var(--accent-color);
            transform: translateY(-3px);
        }
        .price-card.featured {
            border-color: var(--accent-color);
            background: var(--bg-panel);
            box-shadow: 0 0 25px var(--accent-glow);
        }
        .price-badge {
            position: absolute;
            top: -10px;
            right: 18px;
            background: var(--accent-gradient);
            color: #fff;
            font-size: 9px;
            font-weight: 900;
            letter-spacing: 0.1em;
            padding: 3px 8px;
            border-radius: 999px;
            text-transform: uppercase;
        }
        .plan-name { font-size: 1rem; font-weight: 800; color: #ffffff; }
        .plan-price { font-size: 1.9rem; font-weight: 900; color: #ffffff; }
        .plan-price span { font-size: 0.8rem; font-weight: 500; color: #a49498; }
        .plan-features { list-style: none; display: flex; flex-direction: column; gap: 8px; font-size: 0.82rem; color: #d0c5ca; }
        .plan-features li::before { content: "✓ "; color: var(--accent-color); font-weight: 800; }
        .plan-btn {
            margin-top: auto;
            background: var(--bg-sidebar);
            border: 1px solid var(--border-color);
            color: #ffffff;
            padding: 10px;
            border-radius: 8px;
            font-weight: 700;
            font-size: 0.85rem;
            cursor: pointer;
            text-align: center;
            text-decoration: none;
            transition: all 0.15s;
        }
        .plan-btn:hover, .price-card.featured .plan-btn {
            background: var(--accent-gradient);
            border-color: var(--accent-color);
            box-shadow: 0 0 14px var(--accent-glow);
        }

        /* ── Responsive ── */
        @media (max-width: 920px) {
            header { padding: 0 20px; }
            .hero-container { grid-template-columns: 1fr; }
            .hero-title { font-size: 2.1rem; }
            .pricing-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>

    <header>
        <a href="/" class="nav-brand">
            <img src="{{ custom_logo_url or '/static/img/crimson_paw_logo.png' }}" alt="{{ platform_name or 'Crimson Paw' }}" class="nav-brand-logo">
            <div class="nav-brand-text">
                <span class="nav-brand-title">{{ platform_name or 'CRIMSON PAW' }}</span>
                <span class="nav-brand-sub">ENTERPRISE RED TEAM PENTEST SUITE</span>
            </div>
        </a>
        <nav class="nav-links">
            <a href="/" class="nav-link">Home</a>
            <span class="nav-link" onclick="openPricingModal()">Pricing</span>
            <a href="/dashboard" class="nav-btn-signin">Sign in</a>
        </nav>
    </header>

    <main>
        <div class="hero-container">
            <!-- Left Hero Card -->
            <div class="hero-card">
                <div class="hero-tag">{{ platform_name or "CRIMSON PAW" }}</div>
                <h1 class="hero-title">Authorized link infrastructure for legal red-team operations.</h1>
                <p class="hero-desc">
                    {{ platform_name or 'Crimson Paw' }} is built for authorized cyber security teams, approved red-team operators, and lawful pentesters who need controlled link services for sanctioned engagement workflows.
                </p>
                <p class="hero-desc-sec">
                    Purchase a plan, generate the permitted number of links included in your tier, and run engagement-ready link operations inside approved scopes for internal testing, simulations, and defensive validation.
                </p>
                <button type="button" class="hero-cta-btn" onclick="openPricingModal()">VIEW PRICING</button>
            </div>

            <!-- Right Hero Column -->
            <div class="hero-right-col">
                <div class="logo-card">
                    <img src="{{ custom_logo_url or '/static/img/crimson_paw_logo.png' }}" alt="{{ platform_name or 'Platform' }} Emblem" class="logo-card-img">
                </div>
                <div class="disclaimer-card" onclick="openDisclaimerModal()" style="cursor: pointer;">
                    <div class="disclaimer-icon-wrap">⚠️</div>
                    <div class="disclaimer-content">
                        <span class="disclaimer-label">DISCLAIMER</span>
                        <span class="disclaimer-text">Authorized educational use only. Open the full disclaimer before purchasing or using any service.</span>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Pricing Modal -->
    <div id="pricing-modal" class="modal-backdrop" onclick="closeModalOnBackdrop(event, 'pricing-modal')">
        <div class="pricing-modal">
            <button class="modal-close" onclick="closeModal('pricing-modal')">&times;</button>
            <div class="pricing-header">
                <h2>SUBSCRIPTION PLANS</h2>
                <p>Every plan includes a fully isolated client dashboard, dedicated deployment domains, and full platform access.</p>
            </div>
            <div class="pricing-grid">
                <div class="price-card">
                    <div class="plan-name">2 WEEKS</div>
                    <div class="plan-price">$250 <span>/ 2 weeks</span></div>
                    <ul class="plan-features">
                        <li>1 Deployment Domain Included</li>
                        <li>Isolated Client Dashboard</li>
                        <li>Link Studio — Deploy & Capture</li>
                        <li>Real-Time Telegram Capture Alerts</li>
                        <li>Mailbox, Keyword Alerts & B2B Sender</li>
                    </ul>
                    <a href="/dashboard" class="plan-btn">Launch Deployment</a>
                </div>
                <div class="price-card featured">
                    <div class="price-badge">RECOMMENDED</div>
                    <div class="plan-name">1 MONTH</div>
                    <div class="plan-price">$350 <span>/ month</span></div>
                    <ul class="plan-features">
                        <li>2 Deployment Domains Included</li>
                        <li>Isolated Client Dashboard</li>
                        <li>Link Studio — Deploy & Capture</li>
                        <li>Real-Time Telegram Capture Alerts</li>
                        <li>Mailbox, Keyword Alerts & B2B Sender</li>
                    </ul>
                    <a href="/dashboard" class="plan-btn">Launch Deployment</a>
                </div>
                <div class="price-card">
                    <div class="plan-name">2 MONTHS</div>
                    <div class="plan-price">$650 <span>/ 2 months</span></div>
                    <ul class="plan-features">
                        <li>4 Deployment Domains Included</li>
                        <li>Isolated Client Dashboard</li>
                        <li>Link Studio — Deploy & Capture</li>
                        <li>Real-Time Telegram Capture Alerts</li>
                        <li>Mailbox, Keyword Alerts & B2B Sender</li>
                    </ul>
                    <a href="/dashboard" class="plan-btn">Launch Deployment</a>
                </div>
            </div>
        </div>
    </div>

    <!-- Disclaimer Modal -->
    <div id="disclaimer-modal" class="modal-backdrop" onclick="closeModalOnBackdrop(event, 'disclaimer-modal')">
        <div class="pricing-modal" style="max-width: 600px;">
            <button class="modal-close" onclick="closeModal('disclaimer-modal')">&times;</button>
            <div class="pricing-header" style="text-align: left;">
                <h2 style="color: #ff3b45; display: flex; align-items: center; gap: 8px;">⚠️ LEGAL DISCLAIMER</h2>
                <p style="margin-top: 10px; line-height: 1.6; color: #d0c5ca;">
                    {{ platform_name or 'Crimson Paw' }} is designed strictly for authorized cybersecurity auditing, red-team assessments, and penetration testing simulations conducted with written permission from the target asset owner. Unauthorized access or use against non-consenting systems is illegal under applicable federal and international cybersecurity laws.
                </p>
            </div>
            <div style="display: flex; justify-content: flex-end; margin-top: 20px;">
                <button type="button" class="hero-cta-btn" style="padding: 9px 24px;" onclick="closeModal('disclaimer-modal')">I UNDERSTAND</button>
            </div>
        </div>
    </div>

    <script>
        function openPricingModal() {
            document.getElementById('pricing-modal').classList.add('open');
        }
        function openDisclaimerModal() {
            document.getElementById('disclaimer-modal').classList.add('open');
        }
        function closeModal(id) {
            document.getElementById(id).classList.remove('open');
        }
        function closeModalOnBackdrop(e, id) {
            if (e.target.id === id) closeModal(id);
        }
    </script>
</body>
</html>
'''
