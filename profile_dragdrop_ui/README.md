# Profile Drag & Drop (Simple)

Tiny PySide6 GUI that loads a JSON file and shows fields as draggable items.

- Drag a field from the left list
- Drop into the pad on the right
- The dropped value is appended and copied to clipboard

## Install
```bash
python -m pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Safety
Keys that look like payment card data (card number / CVV / expiry) are excluded and shown in the "Excluded" box.
