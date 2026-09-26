# Qt 6.11.1 original attribution archive

This directory preserves original `qt_attribution.json` files, associated
`LicenseFile` texts, and `LICENSES/` templates from five fixed-version Qt
6.11.1 source archives. [`index.json`](index.json) records the official archive
URL and SHA-256, module, original source path, local path, and available text
hashes. The original files are preserved byte for byte, including upstream
formatting; use the index to navigate them.

The archive covers Qt modules found in the local Windows installer candidate:
Base (Core, Gui, Network, Test), Declarative (Qml, Quick), Multimedia, SVG,
and Image Formats. Source attribution metadata can also mention code that the
particular Windows wheel did not compile or that RecurGO excludes at packaging
time, including the FFmpeg media backend. Presence here does not mean a binary
is shipped. The installer's `file-manifest.json` is the inventory of shipped
files. For directly identified plugin notices, see
[`../third_party/README.md`](../third_party/README.md).

These texts retain upstream terms; RecurGO's MIT license does not replace
them. The archive is a source-backed notice collection, not a claim that all
binary redistribution conditions have been completed.
