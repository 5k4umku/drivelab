# Third party notices

The application bootstrap downloads pinned files with SHA-256 verification. Versions and hashes are in `vendor/manifest.json`. The deployable build includes these files; large generated runtime assets are not committed to Git.

| Component | Version | License | Purpose |
|---|---|---|---|
| Pyodide | 0.27.7 | BSD-3-Clause | CPython in WebAssembly |
| CPython | 3.12.7 (Pyodide build) | PSF | Numerical kernel |
| Three.js | 0.180.0 | MIT | Parametric 3D rendering |
| docx | 9.6.1 | MIT | Editable DOCX generation |
| JSZip, included in docx browser build | 3.10.1 | MIT / GPLv3, used under MIT | OOXML ZIP packaging |
| Manrope and IBM Plex Mono | Google Fonts distribution | SIL Open Font License | Interface typography |

License texts for the runtime libraries are retained in `vendor/`. Font requests go to Google Fonts; project inputs are never included in these requests. System font fallbacks remain functional when fonts are unavailable.

Original seminar photographs and copies of GOST publications are not distributed. Tables used for computation have source descriptions. Formula references are documented in `docs/gost-clauses.md`.
