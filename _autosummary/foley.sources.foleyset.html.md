# foley.sources.foleyset

FoleySet — a CC-BY, Foley-native starter corpus (Ring 0).

FoleySet (report 11 §3.2) is a Creative-Commons-BY dataset of Foley recordings
organized by a two-level Foley taxonomy in its directory structure. It is a
ship-in-repo Ring-0 corpus: uniform `CC-BY-4.0` (attribution required), stored
by-value (cacheable), with the folder-path taxonomy carried as tag hints.

Ingesting requires the user to have downloaded FoleySet locally; this adapter
only enumerates + licenses it (see [`foley.sources.base`](foley.sources.base.html.md#module-foley.sources.base)).

### Module Attributes

| [`FOLEYSET`](#foley.sources.foleyset.FOLEYSET)   | The FoleySet Ring-0 adapter (uniform CC-BY, folder-path tag hints).   |
|-------------------------------------------------------------|-----------------------------------------------------------------------|

### foley.sources.foleyset.FOLEYSET *= UniformCorpus(name='foleyset', ring=0, default_license_id='CC-BY-4.0', source='foleyset', rights_verified=True, tag_hints_from_path=True)*

The FoleySet Ring-0 adapter (uniform CC-BY, folder-path tag hints).
