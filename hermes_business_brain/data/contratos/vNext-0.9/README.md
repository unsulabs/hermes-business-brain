# vNext-0.9 handoff contract artifacts

`Esquema_Manifiesto_vNext.schema.json` is a byte-verbatim copy of the product's
contract JSON Schema (`contratos/vNext-0.9/`), vendored at the upstream commit
`8803b1bc766092f78b5f65bd83890057e7b749ba`. It is the schema enforced by the
vendored engine validator `hermes_business_brain/engine/validador_de_traspaso.py`.

The validator resolves the schema next to the manifest first (upstream layout,
where the schema ships inside the handoff package); when a user imports a
package that does not carry its own copy, the engine falls back to this shipped
copy so the layout requirement stays implicit.
