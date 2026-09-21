---
schema: "agora-ai-sdlc/artifact/v1"
kind: "impact-analysis"
version: 1
id: "IMA-001"
work: "cross-repo-change"
revision: 2
traces-to: ["UOW-001", "PLN-001", "BLP-001"]
unit: "UOW-001"
plan: "PLN-001"
bolt-plans: ["BLP-001"]
repositories:
  - id: "payments-api"
    ref: "repo:payments-api"
  - id: "billing-domain"
    ref: "repo:billing-domain"
  - id: "customer-web"
    ref: "repo:customer-web"
components:
  - repository: "payments-api"
    name: "RecurringPaymentController"
    expected-change: "Expose recurring-payment creation."
  - repository: "billing-domain"
    name: "BillingSchedule"
    expected-change: "Persist recurring billing cadence."
  - repository: "customer-web"
    name: "RecurringPaymentForm"
    expected-change: "Collect recurring-payment parameters."
contracts:
  - type: "api"
    name: "POST /recurring-payments"
    repository: "payments-api"
    expected-change: "Add request/response contract."
  - type: "event"
    name: "RecurringPaymentCreated"
    repository: "billing-domain"
    expected-change: "Publish versioned event payload."
dependencies:
  - source: "customer-web"
    target: "payments-api"
    direction: "outbound"
    status: "known"
    reason: null
  - source: "payments-api"
    target: "billing-domain"
    direction: "outbound"
    status: "known"
    reason: null
  - source: "billing-domain"
    target: "customer-web"
    direction: "unknown"
    status: "unknown"
    reason: "Consumer of the new event has not been confirmed."
expected-changes:
  - "Add recurring payment endpoint."
  - "Add billing schedule persistence and event."
  - "Update customer UI."
owners: ["team-payments", "team-billing", "team-web"]
reviewers: ["enterprise-architect", "team-payments"]
confidence: "medium"
unknowns:
  - "Confirm whether customer-web consumes RecurringPaymentCreated directly."
approval-state: "approved"
approved-by: "enterprise-architect"
approved-revision: 2
required-sections: ["Scope", "Repositories", "Components and contracts", "Dependencies", "Expected changes", "Unknowns", "Approval"]
---
# Impact analysis

## Scope

Recurring payments across payment, billing, and customer-web repositories.

## Repositories

Three provider-neutral repository identifiers are affected.

## Components and contracts

API and event contracts cross repository boundaries.

## Dependencies

Known dependency directions are recorded; one event consumer remains explicitly unknown.

## Expected changes

The change spans API, domain persistence/eventing, and UI.

## Unknowns

The event consumer relationship remains unresolved and must not be silently inferred.

## Approval

Approved by enterprise-architect at revision 2.
