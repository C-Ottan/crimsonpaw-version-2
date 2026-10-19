import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('icebadger.db')
c = conn.cursor()

# 1. Insert 2 sample operators
c.execute("DELETE FROM operators WHERE username IN ('op_alpha', 'op_recon')")
c.execute("DELETE FROM operator_assignments WHERE operator_id NOT IN (SELECT id FROM operators)")

pwd_hash_alpha = generate_password_hash("OperatorPass2026!")
pwd_hash_recon = generate_password_hash("ReconAccess2026!")

c.execute("""
    INSERT INTO operators (username, password_hash, role, status, token, created_at, last_login)
    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""", ('op_alpha', pwd_hash_alpha, 'operator', 'active', 'a1b2c3d4e5f6'))
op_alpha_id = c.lastrowid

c.execute("""
    INSERT INTO operators (username, password_hash, role, status, token, created_at, last_login)
    VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
""", ('op_recon', pwd_hash_recon, 'operator', 'active', 'f6e5d4c3b2a1'))
op_recon_id = c.lastrowid

# Assign victim sessions
c.execute("INSERT INTO operator_assignments (operator_id, session_user_code) VALUES (?, ?)", (op_alpha_id, 'DVWRHR76J'))
c.execute("INSERT INTO operator_assignments (operator_id, session_user_code) VALUES (?, ?)", (op_recon_id, 'D63QP7TSH'))

# 2. Insert realistic keyword surveillance matches
c.execute("DELETE FROM keyword_matches")
c.execute("""
    INSERT INTO keyword_matches (rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime, is_triaged, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-2 hours'), 0, datetime('now', '-2 hours'))
""", (1, 'DVWRHR76J', 'Tyrone McLeod', 'Info@proroofsales.com', 'wire transfer', 'URGENT: Outstanding Vendor Invoice & Wire Transfer Details', 'accounting@acme-corp.com', 'Please execute the wire transfer of $142,500.00 to the attached bank routing details.', 'msg_001_wire'))

c.execute("""
    INSERT INTO keyword_matches (rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime, is_triaged, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-45 minutes'), 0, datetime('now', '-45 minutes'))
""", (2, 'D63QP7TSH', 'Marcus Vanceley', 'MarcusVanceley@AxiomTechnologyGroup.onmicrosoft.com', 'password', 'Fwd: Temporary Admin Password & Azure MFA Reset', 'it-support@axiomtech.com', 'Here is your temporary password for the Azure tenant admin account: P@ssw0rd99!', 'msg_002_pwd'))

c.execute("""
    INSERT INTO keyword_matches (rule_id, session_user_code, victim_name, victim_email, matched_keyword, email_subject, email_sender, email_snippet, message_id, received_datetime, is_triaged, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', '-10 minutes'), 0, datetime('now', '-10 minutes'))
""", (3, 'DRBQKN6ES', 'Hatmar Canary', 'hatmarcanary@AxiomTechnologyGroup.onmicrosoft.com', 'confidential', 'STRICTLY CONFIDENTIAL: Acquisition Strategy Q4', 'ceo@axiomtech.com', 'This draft contains confidential terms regarding the target company acquisition.', 'msg_003_conf'))

conn.commit()
conn.close()
print("Rich operational data staged successfully in icebadger.db!")
