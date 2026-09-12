# formDialog() API

`formDialog` is injected into every Form Script as `this.formDialog`. Implementation: `frontend/src/utils/renderFieldLayoutDialog.js`.

## Usage

```js
const data = await this.formDialog({
  title: 'Lost reason',
  fields: [
    { fieldname: 'lost_reason', fieldtype: 'Link', options: 'CRM Lost Reason', reqd: 1 },
    { fieldname: 'notes', fieldtype: 'Small Text' },
  ],
})
if (!data) return // cancelled
```

```js
this.formDialog({
  title: 'Quick note',
  fields: [{ fieldname: 'content', fieldtype: 'Text Editor' }],
  onSubmit(data) {
    return this.call('crm.api.notes.create', data)
  },
})
```

## Options

| Option | Meaning |
|---|---|
| `title` | Dialog title |
| `doctype` | Load that doctype's Quick Entry layout |
| `tabs` | Full layout: tabs → sections → columns → fields |
| `fields` | Flat field list (wrapped in one section) |
| `fieldnames` | Pick fields from doctype meta |
| `defaults` | Pre-fill values |
| `required` | Extra required fieldnames |
| `size` | Dialog size (default `xl`) |
| `actions` | Custom buttons; overrides default submit |
| `onSubmit` | Called with data before close; throw to keep the dialog open |
| `onCancel` | Cancel / dismiss |
| `submitLabel` / `cancelLabel` | Button labels |

Returns a Promise that resolves to the field data object, or `null` if cancelled.
