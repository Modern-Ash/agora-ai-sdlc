# Private-offer input boundary

Prepare each private offer in an access-controlled sales/legal system and the AWS Marketplace workflow, not in this public repository. This file defines required inputs but contains no customer, buyer, pricing, payment, credential, or negotiated-term values.

## Buyer and offer identity

- Marketplace product and offer owner.
- Buyer legal entity and authorized procurement contacts.
- Eligible buyer AWS account identifiers and, when applicable, private-marketplace administrator account.
- Offer name, expiration, contract duration, renewal treatment, and target acceptance date.

All values above are customer-specific or operational records. Keep them outside Git and provide access only to authorized commercial and legal participants.

## Scope and statement of work

- Selected service dimension and exact package baseline.
- Customer problem, repositories, teams, environments, and bounded Unit of Work or rollout cohort.
- Prerequisites, activities, deliverables, evidence boundaries, exclusions, assumptions, dependencies, and change-control process.
- Customer and Modern Ash responsibilities, access method, data handling, support window, named acceptance owners, and exit criteria.
- Measured baseline and customer-agreed goals without guaranteed percentages or outcomes.
- AWS services or associated Marketplace products directly supported by the engagement, including any customer-incurred infrastructure charges.

Start from the published [service packages](../README.md), [reference architecture](../reference-architecture.md), and [shared-responsibility model](../security-and-responsibility.md). Customer-specific terms override no technical limitation unless an approved implementation actually supplies the missing capability.

## Commercial and legal inputs

- Approved pricing dimension, negotiated consideration, currency, payment schedule, taxes, and offer duration.
- Approved statement of work, legal terms, order documents, and any required addenda.
- Refund, cancellation, warranty, liability, intellectual-property, confidentiality, privacy, security, and data-processing terms approved by accountable counsel.
- Seller eligibility, tax, banking, and Marketplace account readiness confirmed by marketplace operations.

Do not commit these values or documents here. The repository is neither a pricing system nor a customer contract store.

## Delivery and support inputs

- Public listing support contact owned by an operating team.
- Pre-purchase response owner and post-acceptance kickoff owner.
- Engagement channels, hours, response expectations, escalation route, start/end dates, and handoff at completion.
- Explicit statement of whether any on-site work, production access, AWS resource provisioning, custom integration, or ongoing support is included.
- Incident, backup, credential, key, identity, monitoring, and production-operation owners.

Engagement support must not be described as managed operations or a software SLA. Any broader obligation needs a separately reviewed service design, staffing model, terms, and marketplace dimension.

## Final offer gate

Before creating or sending an offer, accountable owners must:

1. Complete the [pre-submission review](review-checklist.md) against the exact portal copy and attachments.
2. Confirm that buyer identifiers, pricing, terms, support contacts, and attachments are in approved systems only.
3. Validate the related AWS service or public Marketplace product and document how the engagement supports it.
4. Check that every technical statement remains within the [claim register](claim-substantiation.md).
5. Verify all infrastructure costs, access requirements, acceptance criteria, and exclusions with the buyer.

Marketplace submission and offer creation remain separate business actions; this repository does not authorize either action.
