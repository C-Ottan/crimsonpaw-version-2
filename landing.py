# ── landing.py ──────────────────────────────────────────────
# Crimson Paw Public Landing Page Template
# Fully authentic replica of the crystal red-team pentest suite design

CRIMSON_PAW_LANDING_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CRIMSON PAW — Crystal-Powered Pentest Suite</title>
    <link rel="icon" type="image/png" href="/static/img/crimson_paw_logo.png">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #0b070a;
            background-image: 
                radial-gradient(circle at 50% 15%, rgba(229, 9, 20, 0.16) 0%, transparent 60%),
                radial-gradient(circle at 85% 60%, rgba(180, 7, 16, 0.10) 0%, transparent 50%),
                linear-gradient(135deg, rgba(229, 9, 20, 0.04) 25%, transparent 25%),
                linear-gradient(225deg, rgba(229, 9, 20, 0.04) 25%, transparent 25%),
                linear-gradient(45deg, rgba(229, 9, 20, 0.04) 25%, transparent 25%),
                linear-gradient(315deg, rgba(229, 9, 20, 0.04) 25%, #0b070a 25%);
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
            background: rgba(11, 7, 10, 0.75);
            backdrop-filter: blur(14px);
            border-bottom: 1px solid rgba(229, 9, 20, 0.15);
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
            border: 1px solid rgba(229, 9, 20, 0.35);
            box-shadow: 0 0 14px rgba(229, 9, 20, 0.4);
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
            color: #ff3b45;
        }
        .nav-btn-signin {
            background: linear-gradient(135deg, #e50914, #b80711);
            color: #ffffff;
            padding: 8px 24px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 700;
            text-decoration: none;
            box-shadow: 0 0 18px rgba(229, 9, 20, 0.5);
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(255, 255, 255, 0.15);
        }
        .nav-btn-signin:hover {
            background: linear-gradient(135deg, #ff1f2a, #d40813);
            box-shadow: 0 0 24px rgba(229, 9, 20, 0.7);
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
            background: rgba(18, 12, 16, 0.84);
            border: 1px solid rgba(229, 9, 20, 0.26);
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
            background: radial-gradient(circle, rgba(229, 9, 20, 0.18) 0%, transparent 70%);
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
            background: #e50914;
            box-shadow: 0 0 8px #e50914;
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
            background: linear-gradient(135deg, #e50914, #b00710);
            color: #ffffff;
            padding: 13px 34px;
            border-radius: 9999px;
            font-size: 12.5px;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border: 1px solid rgba(255, 255, 255, 0.2);
            cursor: pointer;
            box-shadow: 0 6px 26px rgba(229, 9, 20, 0.5);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
        }
        .hero-cta-btn:hover {
            background: linear-gradient(135deg, #ff1f2a, #cc0813);
            box-shadow: 0 8px 32px rgba(229, 9, 20, 0.7);
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
            border: 1px solid rgba(229, 9, 20, 0.28);
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
            border-color: rgba(229, 9, 20, 0.5);
        }
        .logo-card::after {
            content: '';
            position: absolute;
            inset: 0;
            background: radial-gradient(circle at 50% 50%, rgba(229, 9, 20, 0.2) 0%, transparent 70%);
            pointer-events: none;
        }
        .logo-card-img {
            width: 84%;
            height: 84%;
            object-fit: contain;
            filter: drop-shadow(0 0 30px rgba(229, 9, 20, 0.45));
            position: relative;
            z-index: 2;
        }

        /* Disclaimer Card */
        .disclaimer-card {
            width: 100%;
            max-width: 360px;
            background: rgba(18, 12, 16, 0.85);
            border: 1px solid rgba(229, 9, 20, 0.24);
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
            background: rgba(229, 9, 20, 0.16);
            border: 1px solid rgba(229, 9, 20, 0.35);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            color: #ff3b45;
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
            background: #140d11;
            border: 1px solid rgba(229, 9, 20, 0.35);
            border-radius: 24px;
            max-width: 960px;
            width: 100%;
            padding: 36px 40px;
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.8), 0 0 40px rgba(229, 9, 20, 0.2);
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
            background: #1a1015;
            border: 1px solid #3d1419;
            border-radius: 18px;
            padding: 24px 22px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            position: relative;
            transition: border-color 0.2s, transform 0.2s;
        }
        .price-card:hover {
            border-color: #e50914;
            transform: translateY(-3px);
        }
        .price-card.featured {
            border-color: #e50914;
            background: linear-gradient(180deg, #241117 0%, #160e12 100%);
            box-shadow: 0 0 25px rgba(229, 9, 20, 0.25);
        }
        .price-badge {
            position: absolute;
            top: -10px;
            right: 18px;
            background: #e50914;
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
        .plan-features li::before { content: "✓ "; color: #e50914; font-weight: 800; }
        .plan-btn {
            margin-top: auto;
            background: #281419;
            border: 1px solid #5a1c24;
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
            background: #e50914;
            border-color: #e50914;
            box-shadow: 0 0 14px rgba(229, 9, 20, 0.45);
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
            <img src="/static/img/crimson_paw_logo.png" alt="Crimson Paw" class="nav-brand-logo">
            <div class="nav-brand-text">
                <span class="nav-brand-title">CRIMSON PAW</span>
                <span class="nav-brand-sub">CRYSTAL-POWERED PENTEST SUITE - LEGAL USE ONLY</span>
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
                <div class="hero-tag">CRIMSON PAW</div>
                <h1 class="hero-title">Authorized link infrastructure for legal red-team operations.</h1>
                <p class="hero-desc">
                    Crimson Paw is built for authorized cyber security teams, approved red-team operators, and lawful pentesters who need controlled link services for sanctioned engagement workflows.
                </p>
                <p class="hero-desc-sec">
                    Purchase a plan, generate the permitted number of links included in your tier, and run engagement-ready link operations inside approved scopes for internal testing, simulations, and defensive validation.
                </p>
                <button type="button" class="hero-cta-btn" onclick="openPricingModal()">VIEW PRICING</button>
            </div>

            <!-- Right Hero Column -->
            <div class="hero-right-col">
                <div class="logo-card">
                    <img src="/static/img/crimson_paw_logo.png" alt="Crimson Paw Emblem" class="logo-card-img">
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
                <h2>OPERATIONAL TIERS</h2>
                <p>Select an authorized tier to configure your dedicated deployment infrastructure.</p>
            </div>
            <div class="pricing-grid">
                <div class="price-card">
                    <div class="plan-name">OPERATOR</div>
                    <div class="plan-price">$149 <span>/ month</span></div>
                    <ul class="plan-features">
                        <li>5 Active Deployments</li>
                        <li>Standard S/B/A/R Modes</li>
                        <li>Token Harvesting Telemetry</li>
                        <li>Automatic Office 365 Device Auth</li>
                        <li>Community Knowledge Base</li>
                    </ul>
                    <a href="/dashboard" class="plan-btn">Launch Deployment</a>
                </div>
                <div class="price-card featured">
                    <div class="price-badge">RECOMMENDED</div>
                    <div class="plan-name">RED TEAM PRO</div>
                    <div class="plan-price">$349 <span>/ month</span></div>
                    <ul class="plan-features">
                        <li>25 Active Deployments</li>
                        <li>Live Registrar Domain Binding</li>
                        <li>AI Phishing Content Synthesizer</li>
                        <li>Full Graph API Exfiltration Suite</li>
                        <li>Multi-tenant Session Refresher</li>
                    </ul>
                    <a href="/dashboard" class="plan-btn">Launch Deployment</a>
                </div>
                <div class="price-card">
                    <div class="plan-name">ENTERPRISE SCOPE</div>
                    <div class="plan-price">$799 <span>/ month</span></div>
                    <ul class="plan-features">
                        <li>Unlimited Deployments</li>
                        <li>Dedicated B2B SMTP Nodes</li>
                        <li>Automated Subdomain Rotation</li>
                        <li>Custom C2 Payload Webhooks</li>
                        <li>24/7 Security Operations Access</li>
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
                    Crimson Paw is designed strictly for authorized cybersecurity auditing, red-team assessments, and penetration testing simulations conducted with written permission from the target asset owner. Unauthorized access or use against non-consenting systems is illegal under applicable federal and international cybersecurity laws.
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
