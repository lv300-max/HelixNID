# How It Works

1. A shipment reaches carrier handoff.
2. HELIXNID reads only facts known at that point.
3. The scoring engine finds the strongest supported historical pattern.
4. It adjusts the original delivery promise.
5. It produces late probability, risk band, confidence, and warning time.
6. The API returns the result with model/data identity for replay.
7. The dashboard shows the result without duplicating scoring logic.

V1 accepts carrier/service fields, but the locked Olist evidence does not identify FedEx/UPS/DHL brands, so brand-specific learned effects remain evidence-gated.
