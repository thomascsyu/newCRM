# Future form-scripting work

Completed work lives in [ARCHIVE.md](./ARCHIVE.md). Do not re-spec shipped APIs here.

## 3B — List-view class scripts

`getScript` already accepts a `view` argument (`Form` / `List` on `CRM Form Script`), but `useDocument` is the only caller and always uses Form.

- Wire List scripts through the same class engine (or document why the legacy `list_script` + `setupListCustomizations` path stays).
- File scripts: `frontend/src/doctypes/<doctype>/list.js`.

## 4 — Vue tests for the scripting UI

Unit tests cover pure utils only. Add component tests for:

- `FieldLayout` + `setFieldProperty` visibility/mandatory
- `formDialog()` submit / cancel / validation
- `FieldLayoutDialog` standalone context (no `useDocument`)

Do not try to mount every CRM page.

## 5 — Frontend file script for CRM Products

Line math today runs as a server-side standard script. A Vue file script (`frontend/src/doctypes/crm_products/form.js`) would keep qty/rate/discount updates instant while editing a lead/deal, matching Task/Note file scripts.

## 6 — Validate without try/catch

`save.submit` still catches thrown `validate`. Long-term: change frappe-ui `validate` to return an error message, then drop the wrapper try/catch in `frontend/src/data/document.js`.
