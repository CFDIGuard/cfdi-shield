# Bank Shield v0.1

Bank Shield v0.1 is the current internal banking and reconciliation capability
inside CFDI Shield v1.1 and the first banking-oriented building block of Shield
Suite.

## Current purpose

This module scope currently covers:

- bank statement ingestion from CSV and XLSX
- parsing and normalization of bank movements
- automatic matching against CFDI invoices
- manual reconciliation actions
- reconciliation summaries and exports

## Current implementation status

Bank Shield v0.1 is intentionally still implemented inside the legacy shared
application structure. No runtime logic has been moved into
`app/modules/bank_shield/` yet.

This directory currently exists to:

- name the module explicitly
- document its boundaries
- prepare a safe future migration path

## Current source components

- `app/services/bank_statement_parser.py`
- `app/services/bank_reconciliation_service.py`
- `app/models/bank_transaction.py`
- `app/repositories/bank_transaction_repository.py`
- `app/schemas/bank_reconciliation.py`
- `app/web/routes_pages.py` (`/reconciliation` flows)
- `app/services/excel_exporter.py` (CONCILIACION sheet)
- `templates/reconciliation.html`

## Important constraints

At this stage Bank Shield must not:

- break existing CFDI Shield routes
- change table names or models
- split into a separate app
- change imports or runtime ownership boundaries prematurely

## Next milestone

The next safe step is to strengthen documentation and test coverage around the
current banking behavior before any file movement or refactor.
