# Bank Shield v0.1 Boundary

## What belongs to Bank Shield today

Bank Shield v0.1 currently includes these functional areas:

- bank statement parsing
- reconciliation scoring and classification
- persisted bank movement records
- manual confirmation, rejection, and assignment flows
- banking-related export content

## Current file boundary

Primary components:

- `app/services/bank_statement_parser.py`
- `app/services/bank_reconciliation_service.py`
- `app/models/bank_transaction.py`
- `app/repositories/bank_transaction_repository.py`
- `app/schemas/bank_reconciliation.py`

Connected delivery layer:

- `app/web/routes_pages.py`
- `templates/reconciliation.html`
- `app/services/excel_exporter.py`
- `app/api/routes/dashboard.py`

## Shared dependencies that must stay stable

Bank Shield currently depends on shared platform and CFDI data through:

- `Invoice`
- `InvoiceRepository`
- current user / organization scoping
- shared Excel export pipeline
- shared web routing layer

## What should not move yet

These areas should remain untouched during Bank Shield v0.1 documentation
phase:

- authentication
- session handling
- CSRF
- CFDI parsing
- fiscal validation logic
- public route names
- database schema names

## Migration note

Any future modular migration should happen only after coverage is sufficient for:

- reconciliation upload
- reconciliation filtering
- confirm / reject / assign flows
- Excel export behavior
- multiuser isolation
