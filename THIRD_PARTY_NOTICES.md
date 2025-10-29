Third-Party Notices

This project uses the following third-party software and services:

- Tesseract OCR — Apache License 2.0
  - Binaries installed locally by the user. Project only invokes the executable.
  - https://github.com/tesseract-ocr/tesseract

- Poppler — GPL (GPL v2.0 or later)
  - Binaries installed locally by the user and invoked through pdf2image.
  - https://poppler.freedesktop.org/

- pdf2image — MIT License
  - https://github.com/Belval/pdf2image

- Pillow — HPND License
  - https://python-pillow.org/

- pytesseract — Apache License 2.0
  - https://github.com/madmaze/pytesseract

- Flask — BSD-3-Clause
  - https://flask.palletsprojects.com/

- pandas — BSD-3-Clause
  - https://pandas.pydata.org/

- openpyxl — MIT License
  - https://openpyxl.readthedocs.io/

- Nominatim (OpenStreetMap) service — ODbL Database License (data) and service usage policies
  - https://operations.osmfoundation.org/policies/nominatim/

Notes
- This application invokes Poppler and Tesseract as external executables. The project’s own source code is licensed under MIT, but use and redistribution of those binaries are subject to their respective licenses.
- Users should comply with the terms of the data sources and services used (e.g., OSM/Nominatim usage policies).
