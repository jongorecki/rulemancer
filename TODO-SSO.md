# TODO: Add SSO to Rulemancer (OIDC + SAML)

Added 2026-07-23. Goal: real, demonstrable SSO/SAML/OAuth experience for the job hunt — support-engineer JDs (Anthropic, Glean, etc.) keep asking for hands-on auth troubleshooting, and right now the resume has zero evidence for it. Doing this the way enterprises actually consume SSO turns that category from "nothing" into "real, verifiable evidence at hobby scale." A cert is not the move here; a repo with a writeup is.

## The plan

### 1. Stand up free identity providers (the two that matter)
- [ ] Okta developer account (developer.okta.com, free tier)
- [ ] Microsoft Entra ID free tier
- These are the IdPs enterprise support teams actually see. Both stay free at this scale.

### 2. Wire Rulemancer as a Service Provider — OIDC first
- [ ] Add OIDC login via a real library (Authlib fits the Python stack) — using libraries correctly IS the professional skill; don't hand-roll token handling
- [ ] Log in against Okta, then against Entra, and note every difference that bites (claims, redirect quirks, token lifetimes)
- Weekend-sized.

### 3. Then SAML (the enterprise one that generates the support tickets)
- [ ] Add SAML SP support (python3-saml or similar)
- [ ] Configure against both IdPs: metadata exchange, ACS URL, attribute mapping
- Multi-IdP is the whole point: attribute mapping differences and metadata quirks are where real enterprise pain lives.

### 4. The breakage lab (this is what makes it resume-worthy)
Deliberately break each of these, watch it fail, diagnose with SAML-tracer (browser extension — the actual daily tool of support engineers), fix it, and write down the symptom → cause chain:
- [ ] Expired/rotated signing certificate
- [ ] Wrong ACS URL
- [ ] Mis-mapped email/name attribute
- [ ] Clock skew between IdP and SP
- [ ] Bonus: bad audience/entity ID

### 5. Write it up
- [ ] README section (or docs/ page): the failure modes, what each looked like from the user side, and how it was diagnosed
- The writeup is the interview material. Symptom-to-root-cause stories are exactly what "hands-on SSO troubleshooting experience" means in a JD.

## What this earns, phrased honestly
"Implemented OIDC and SAML SSO in a personal web project against Okta and Microsoft Entra ID, including attribute mapping and debugging assertion failures." Personal-project framing, public repo link, no enterprise-production inflation.

## Time estimate
- OIDC: one weekend
- SAML + breakage lab + writeup: one more weekend
