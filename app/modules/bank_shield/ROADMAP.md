# Bank Shield Roadmap

## Phase 1 - Naming and boundary definition

Goal:

- formally identify the current banking functionality as Bank Shield v0.1
- document boundaries without moving runtime logic

Delivered in this phase:

- internal module directory
- module README
- boundary documentation
- lightweight source comments in core banking files

## Phase 2 - Structure preparation

Goal:

- prepare `app/modules/bank_shield/` for future migration
- keep production logic in place

Expected work:

- expand module docs
- add module-specific test coverage where needed
- identify adapters needed for routes, exports, and repositories

## Phase 3 - Gradual migration

Goal:

- move banking logic in small safe steps after coverage is strong enough

Recommended migration order:

1. parser helpers
2. reconciliation service
3. repository layer
4. schema helpers
5. route adapters
6. template and export adapters

## Guardrails for future work

- do not break existing `/reconciliation` routes during migration
- do not duplicate live logic in two places for long
- do not separate Bank Shield into another app at this stage
- preserve existing user and organization isolation behavior
