---
schema: agora-ai-sdlc/artifact/v1
kind: migration-slice
version: 1
id: MGS-001
work: feature
revision: 1
traces-to: [MGP-001]
slice-id: checkout-total
independently-deployable: true
source-components: [legacy-checkout]
target-components: [target-checkout]
dependencies: []
behavior-ids: [priced-cart, empty-cart-rounding]
required-sections: [Boundary, Behavior in scope, Conversion, Release and rollback, Acceptance]
---
# Migration slice
## Boundary
Only checkout total calculation changes.
## Behavior in scope
Priced cart and explicitly unknown empty-cart rounding.
## Conversion
Translate calculation behind the unchanged contract.
## Release and rollback
Route can return to the legacy calculator.
## Acceptance
Known behavior is equivalent and unknown behavior is explicitly decided.
