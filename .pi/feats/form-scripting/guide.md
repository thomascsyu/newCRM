# Form scripting user guide

CRM Form Scripts are JavaScript classes stored on **CRM Form Script** records (or as files under `frontend/src/doctypes/`). They run in the browser against the open document.

## Minimal script

```js
class CRMLead {
  onLoad() {
    this.setFieldProperty('source', 'reqd', true)
  }

  status() {
    if (this.doc.status === 'Lost') {
      this.setFieldProperty('lost_reason', 'hidden', false)
    }
  }

  validate() {
    if (!this.doc.email) this.throwError('Email is required')
  }
}
```

The class name is the doctype with spaces removed (`CRM Lead` → `CRMLead`). Child tables use their own class (`CRMProducts`).

## Common helpers

- `this.doc.fieldname` — read/write
- `this.doc.trigger('method')` — call another controller method
- `this.getRow('products', idx)` — child row proxy
- `this.setFieldProperty` / `this.setFieldProperties` / `this.removeFieldProperty`
- `this.call`, `this.toast`, `this.router`, `this.formDialog`

## Apply To

- **Form** — document pages and create/edit dialogs (`useDocument`)
- **List** — stored on the record, but list actions still use the older `setupList` script path

## Validation

Throw or call `this.throwError(message)` from `validate` / `onValidate`. Save is blocked and the message is shown as a toast.
