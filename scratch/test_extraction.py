import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from email_outreach import extract_regex_contacts

sample_html = """
<div>
   <p>Contact Us: sales&#64;acme-industrial.com</p>
   <a href="mailto:support@acme-industrial.com">Email Support</a>
   <p>Obfuscated: billing [at] acme-industrial [dot] com</p>
   <p>Obfuscated 2: contact (at) acme-industrial.com</p>
   <p>Obfuscated 3: help at acme-industrial dot com</p>
</div>
"""

result = extract_regex_contacts(sample_html, source_url="https://acme-industrial.com/contact")
print("Extracted Emails:", result["emails"])
print("Extracted Meta:", result["email_meta"])

assert "sales@acme-industrial.com" in result["emails"], "Missing HTML entity email!"
assert "support@acme-industrial.com" in result["emails"], "Missing mailto email!"
assert "billing@acme-industrial.com" in result["emails"], "Missing obfuscated email 1!"
assert "contact@acme-industrial.com" in result["emails"], "Missing obfuscated email 2!"
assert "help@acme-industrial.com" in result["emails"], "Missing obfuscated email 3!"

print("\n✓ ALL 5 EMAIL EXTRACTION TECHNIQUES VERIFIED 100% SUCCESSFUL!")
