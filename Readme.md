# StampOfficeProject

**A suite of desktop applications for stamp collectors and philatelists.**

StampOfficeProject is a Python-based application suite for creating personalized stamp album pages, managing stamp collections, and maintaining stamp catalogue databases. It provides graphical tools to organize stamps, design printable album pages, track collection status, administer catalogue records, process stamp images, and convert albums from third-party formats.

Originally developed in VBA for Excel in the early 2000s, the project has evolved into a set of Python desktop applications built with PyQt6.

## Applications

The suite consists of five complementary applications:

### 1. StampAlbum — Stamp Album Creator

Create and customize stamp album pages using stamp catalogue data and images.

**Features**

- Design album pages in A4 or US Letter format, in portrait or landscape orientation.
- Browse country-specific stamp catalogues and select stamps by catalogue information.
- Arrange, align, and distribute stamps on a page.
- Use grids, zoom controls, rulers, and guide lines for precise positioning.
- Add text, rich-text content, images, decorative borders, page numbers, and headers.
- Organize pages using a tabbed interface and page thumbnails.
- Undo and redo editing operations.
- Import album layouts from AlbumEasy text files.
- Save and reopen album projects.
- Preview and export individual pages or complete albums to PDF.
- Use localized interfaces and help content.

StampAlbum is designed to provide a flexible, graphical alternative to manually preparing album pages.

### 2. StampCatalogue — Collection Manager

Manage personal stamp collections using the catalogue databases.

**Features**

- Create and manage multiple collections.
- Search catalogue records by country, stamp type, year, and Yvert catalogue number.
- View stamp descriptions, face values, and available photographs.
- Track ownership status, including owned, missing, wanted, and ordered stamps.
- Record stamp condition, quantity, purchase price, and personal notes.
- Generate formatted Excel mancolists (`.xlsx`) for missing or wanted stamps.
- Access country catalogues without modifying their records.

StampCatalogue separates the reference catalogue from personal collection data, allowing the same catalogue to support different collections.

### 3. StampDatabase — Catalogue Administration

Maintain the country-specific stamp databases used by the other applications.

**Features**

- Browse and edit stamp catalogue records.
- Add, modify, and delete stamp records.
- Import and export catalogue data using CSV files.
- Undo and redo database editing operations.
- Inspect catalogue metadata, including author, country, description, version, catalogue, and language.
- Support SQLite and Microsoft Access databases.
- Check the availability of Microsoft Access database support.
- Convert or migrate catalogue data between supported database formats where applicable.

StampDatabase is intended for catalogue maintenance rather than everyday collection tracking.

### 4. StampPhoto — Stamp Photo & Scan Processor

Browse, inspect, and batch-convert stamp photographs and scans into standardized resolutions without altering original files.

**Features**

- Browse image collections (supporting JPG, PNG, BMP, TIFF, and WEBP formats) with natural sorting.
- Search images by filename with prefix matching and wildcard support (`*`, `?`).
- Inspect image metadata, including dimensions, file size, format, DPI resolution, and calculated physical stamp dimensions in millimeters.
- Batch convert images to JPG in low (800 px), medium (1,600 px), or high (2,400 px) resolutions, or generate all three sizes at once.
- Safe file handling: detects existing destination files with options to replace, keep, or cancel; handles EXIF rotation and converts transparent backgrounds to white.
- Non-blocking batch processing with progress tracking, pause/stop capability, and detailed failure reports.
- Multi-language interface (English and French) switchable on the fly.

### 5. AlbumConverter — Batch Album Converter

Convert stamp album files created with external programs into native StampAlbum projects (`.sta`) in batch mode.

**Features**

- Batch convert single or multiple album projects without launching the main StampAlbum editor.
- Support for **AlbumEasy** description files (`.txt`), retaining page setups, margins, borders, titles, text layouts, stamp alignments, and associated images.
- Support for **Feuille Album 4** Excel workbooks (`.xls`, Excel 97–2003), mapping each page sheet, shape group, text description, and embedded picture to StampAlbum structures.
- Flexible conflict resolution for existing destination files (ask, replace, skip, or auto-rename).
- Generates detailed execution reports summarizing converted pages, stamps, warnings, or errors.
- Fully compatible with the StampAlbum ecosystem, sharing its core data structures, models, and importers.

## Architecture

The applications share a common set of resources and work together as a desktop suite.

```text
StampOfficeProject/
├── Databases/       # Master and country catalogue databases
├── Help/            # User manuals and help resources
├── Images/          # Application icons and graphical resources
├── Photos/          # Stamp photographs
├── locale/          # Localization resources
├── StampAlbum/      # Album-page editor and AlbumConverter utility
├── StampCatalogue/  # Collection and mancolist manager
├── StampDatabase/   # Catalogue administration
├── StampPhoto/      # Stamp photo viewer and converter
└── utilities/       # Supporting utilities
```

### Technology stack

| Component | Technology |
|---|---|
| Programming language | Python 3 |
| Desktop interface | PyQt6 |
| Reference databases | SQLite / Microsoft Access |
| Database access | `sqlite3`, optional `pyodbc` |
| Image processing | `Pillow` (PIL) |
| Excel binary parsing | `olefile` (for Feuille Album 4 `.xls` files) |
| Collection export | `openpyxl` |
| Album output | PDF through Qt printing facilities |
| Localization | GNU gettext and Qt translations |

## Requirements

- Python 3.8 or later.
- PyQt6 for graphical interfaces.
- `Pillow` for image batch processing in StampPhoto.
- `olefile` for Feuille Album 4 conversion in AlbumConverter.
- `openpyxl` for Excel mancolist generation in StampCatalogue.
- `pyodbc` and a compatible Microsoft Access ODBC driver for Microsoft Access database support.

SQLite support is provided by Python's standard library and does not require a separate database server.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/bdureau/StampOfficeProject.git
cd StampOfficeProject
```

### 2. Install the Python dependencies

```bash
python -m pip install PyQt6 Pillow olefile openpyxl
```

For Microsoft Access database support, install `pyodbc`:

```bash
python -m pip install pyodbc
```

On Windows, a compatible Microsoft Access Database Engine ODBC driver must also be installed. Its availability depends on the operating system and driver architecture.

### 3. Prepare the application resources

Ensure that the required catalogue databases and resource directories are present.

The applications expect the shared resources to be organized alongside the application directories, including:

- `Databases/`
- `Images/`
- `Photos/`, where stamp photographs are stored
- `Help/`
- `locale/`

The master database and country-specific catalogues must be available in the configured database format.

**Note:** The repository may not include all catalogue databases or stamp photographs required for a complete working installation. Use the appropriate data files for your collection and configuration.

## Running the applications

Run the following commands from the repository root:

### StampAlbum

```bash
python StampAlbum/StampAlbum.py
```

### StampCatalogue

```bash
python StampCatalogue/StampCatalogue.py
```

### StampDatabase

```bash
python StampDatabase/StampDatabase.py
```

### StampPhoto

```bash
python StampPhoto/StampPhoto.py
```

### AlbumConverter

```bash
python StampAlbum/AlbumConverter.py
```

Each application starts its own graphical interface.

## Database organization

The suite uses a master database and country-specific catalogue databases.

### Master database

The master database provides shared reference information, including stamp mount sizes and other global catalogue settings.

### Country databases

Country databases contain stamp catalogue records, including fields such as:

- Catalogue number and year.
- Stamp type or category.
- Face value and colour.
- Description.
- Stamp dimensions.
- Sequence and related catalogue identifiers.

The exact schema depends on the database format and the catalogue data available.

### Personal collections

StampCatalogue maintains collection-specific information separately from the reference catalogues. This includes ownership status, condition, quantities, purchase prices, and notes.

This separation allows catalogue records to be reused across multiple personal collections.

## Typical workflows

### Creating an album

1. Launch StampAlbum (or use AlbumConverter to import existing AlbumEasy or Feuille Album 4 collections).
2. Create or open an album page.
3. Select stamps from the available catalogue.
4. Arrange and align stamps on the page.
5. Add titles, captions, images, and decorative elements.
6. Save the album and export the pages to PDF.

### Preparing pictures

1. Launch StampPhoto.
2. Select the source folder containing stamp scans or photographs.
3. Choose the target resolution (low, medium, high, or all).
4. Run batch conversion to produce optimized JPEG images for albums or mancolists.

### Managing a collection

1. Launch StampCatalogue.
2. Select a country catalogue.
3. Create or select a personal collection.
4. Search for stamps and update their ownership information.
5. Export a mancolist to Excel when needed.

### Maintaining a catalogue

1. Launch StampDatabase.
2. Open the appropriate country database.
3. Review or edit catalogue records.
4. Import or export CSV data as required.
5. Save the changes and verify the catalogue in the other applications.

Always back up catalogue databases before performing bulk imports or significant record changes.

## Language support

The applications include localization support for English and French.

Translations are managed through gettext catalogs and application-specific language modules. Localized help content is also supported.

## Related project

**Access to SQLite converter:**  
https://github.com/bdureau/accessToSqlite

This companion project is relevant when migrating catalogue databases from Microsoft Access to SQLite.

## Author

**Boris du Reau**

GitHub: https://github.com/bdureau

## License

Please consult the repository's license file for the applicable licensing terms. If the project is intended to be distributed under the MIT License, include the corresponding `LICENSE` file in the repository root.