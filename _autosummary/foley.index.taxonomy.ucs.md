# foley.index.taxonomy.ucs

UCS table loading + the UCS-filename CatID parse (report 04 §5.2, §6.4).

A UCS filename is underscore-delimited with the **CatID first**:

```default
CatID_FXName_CreatorID_SourceID[_UserCategory_UserData].ext
```

Only token 0 (the CatID) carries the controlled taxonomy; it is looked up in the
table (never string-split, since the category prefix is variable-length). The
loader merges the in-code seed with an optional full-table JSON drop under
`taxonomy/data/ucs_full.json` (JSON wins on CatID collision) — open/closed.

### Functions

| [`default_ucs_table`](#foley.index.taxonomy.ucs.default_ucs_table)()                          | The process-wide default UCS table (seed + any JSON drop), built once.     |
|-----------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| [`load_ucs_table`](#foley.index.taxonomy.ucs.load_ucs_table)(\*[, data_dir, include_seed]) | Build the UCS lookup: the seed rows, overridden/extended by a JSON drop.   |
| [`parse_catid_token`](#foley.index.taxonomy.ucs.parse_catid_token)(filename)                  | Return token 0 (the CatID candidate) of a UCS-style filename, else `None`. |
| [`parse_ucs_filename`](#foley.index.taxonomy.ucs.parse_ucs_filename)(filename, \*[, table])    | Parse a UCS-conformant filename to `(ucs_category, ucs_subcategory)`.      |

### foley.index.taxonomy.ucs.default_ucs_table()

The process-wide default UCS table (seed + any JSON drop), built once.

* **Return type:**
  [`UcsTable`](foley.index.taxonomy.model.md#foley.index.taxonomy.model.UcsTable)

### foley.index.taxonomy.ucs.load_ucs_table(, data_dir=None, include_seed=True)

Build the UCS lookup: the seed rows, overridden/extended by a JSON drop.

* **Parameters:**
  * **data_dir** – Directory to look for `ucs_full.json` in (defaults to the
    package’s `taxonomy/data/`). When present, its rows override the
    seed on CatID collision and add the rest of the ~750-row master.
  * **include_seed** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – Start from the in-code seed table (default `True`).
* **Return type:**
  [`UcsTable`](foley.index.taxonomy.model.md#foley.index.taxonomy.model.UcsTable)
* **Returns:**
  A ready [`UcsTable`](foley.index.taxonomy.model.md#foley.index.taxonomy.model.UcsTable).

### foley.index.taxonomy.ucs.parse_catid_token(filename)

Return token 0 (the CatID candidate) of a UCS-style filename, else `None`.

Strips directory and extension; requires at least one `_` (the field
delimiter). Does not validate the token against the table.

* **Return type:**
  [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]

### foley.index.taxonomy.ucs.parse_ucs_filename(filename, , table=None)

Parse a UCS-conformant filename to `(ucs_category, ucs_subcategory)`.

Fail-quiet: returns `(None, None)` when the name is not UCS-conformant or
its CatID token is unknown (so a wrong subcategory is never emitted).

* **Parameters:**
  * **filename** – A path or filename (only the basename’s token 0 is used).
  * **table** ([`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`UcsTable`](foley.index.taxonomy.model.md#foley.index.taxonomy.model.UcsTable)]) – The UCS table to resolve against (defaults to
    [`default_ucs_table()`](#foley.index.taxonomy.ucs.default_ucs_table)).
* **Return type:**
  [`tuple`](https://docs.python.org/3/builtins/stdtypes.html#tuple)[[`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)], [`Optional`](https://docs.python.org/3/library/typing.html#typing.Optional)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]]
