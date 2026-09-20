# Change request: volume pricing

Add a ten-percent volume discount when a catalog quote contains at least ten units.

Acceptance criteria:

- Existing prices and unknown-SKU behavior remain unchanged.
- Quantity must be a positive integer; zero and negative values raise `ValueError`.
- The discount uses exact `Decimal` arithmetic.
- Automated tests cover the threshold and invalid quantities.
