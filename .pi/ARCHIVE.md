# Completed form-scripting work

Planning docs were missing from this checkout. This archive records what is already in the tree so later phases do not rebuild it.

## Engine

- `useDocument` loads the doc, wires scripts, patches `save.submit` with validate + mandatory checks.
- `getScript` evaluates class-based Form Scripts via `new Function`, injects helpers, and supports child-doctype classes.
- `createDocProxy` / `getClassNames` live in `frontend/src/utils/scriptHelpers.js` (unit-tested).
- File scripts exist for `CRM Task` and `FCRM Note`.

## Field layout and dialogs

- `FieldLayout` / `Field` / `Section` / `Column` render doctype layouts.
- Standalone mode accepts a `context` prop (no `useDocument`).
- `formDialog()` pushes onto `fieldLayoutDialogs` and returns a Promise.
- `GlobalModals` mounts `FieldLayoutDialogContainer`.

## Field transforms

Pure, tested helpers in `frontend/src/utils/fieldTransforms.js` and `frontend/src/utils/expressions.js`: `processField`, `findMissingMandatory`, `parseLinkFilters`, depends-on evaluation.

## Decisions already made

- Form Scripts stay as evaluated strings in the browser (no build step).
- List customization stays on the older `setupList` function path.
- Product line totals are a **server-side** standard script (`crm/fcrm/doctype/crm_products/crm_products.py`), not a Vue file script.
- Validate still throws (frappe-ui). The CRM save wrapper toasts the message instead of swallowing it.
- `_assign` equals/not-equals are serialized as LIKE/NOT LIKE because the column stores a JSON array string.
- Currency `options` with `:` are resolved from values already on the current/parent doc; no extra network fetch in list formatters.
