# Form scripting — stable contracts

These APIs are used by CRM Form Script records (evaluated in the browser) and by file scripts under `frontend/src/doctypes/`.

## Script loading

- `getScript(doctype, view = 'Form')` in `frontend/src/data/script.js` loads enabled `CRM Form Script` rows plus optional file modules.
- File modules are globbed from `frontend/src/doctypes/<doctype_slug>/<view_slug>.js`.
- `useDocument` in `frontend/src/data/document.js` calls `setupScript` for Form view only.

## Controller helpers (injected)

| Helper | Role |
|---|---|
| `this.doc` | Proxy over document data; `trigger(method)` and `getRow` are reserved |
| `this.call` | `frappe-ui` `call` |
| `this.toast` | toast |
| `this.router` | Vue router |
| `this.socket` | realtime socket |
| `this.createDialog` | `$dialog` |
| `this.formDialog` | `renderFieldLayoutDialog` |
| `this.throwError(message)` | toast + throw (`alreadyToasted` is set so save does not toast twice) |

## Field property API

```js
this.setFieldProperty(fieldname, property, value, rowName?)
this.setFieldProperties(fieldname, { hidden: true, reqd: true }, rowName?)
this.removeFieldProperty(fieldname, property, rowName?)
this.getField(fieldname)
this.setFieldHtml(fieldname, html)
```

Overrides live on `document.fieldPropertyOverrides` and are merged by `processField()`.

## Document triggers

`onLoad` / `on_load` / `onload`, `onRender` / `on_render` / `refresh`, `onValidate` / `on_validate` / `validate`, `onSave` / `on_save`, `onError` / `on_error`, `onBeforeCreate` / `on_before_create`, plus field-name change handlers and `onRowAdd` / `onRowRemove`.

`validate` may throw. Save shows `getValidationErrorMessage(err)` unless `err.alreadyToasted`.

## formDialog()

See [feats/form-scripting/form-dialog.md](./feats/form-scripting/form-dialog.md).

## List scripts (legacy)

List/bulk actions still use `list_script` + `setupListCustomizations` in `frontend/src/utils/index.js`, not the class-based `getScript` engine.

## Currency options

`resolveCurrency(options, doc, parentDoc, fallback)` in `frontend/src/utils/currency.js` understands:

- `currency` — field on this or parent doc
- `currency:Company` — two-part field hint
- `Company:company:default_currency` — three-part Desk format, using values already on the row
