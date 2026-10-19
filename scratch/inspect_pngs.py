import os
from PIL import Image

for f in ['Adobe.png', 'DocuSign.png', 'Dropbox.png', 'Microsoft 365.png', 'OneDrive.png', 'Outlook.png', 'QuickBooks.png', 'SharePoint.png']:
    if os.path.exists(f):
        img = Image.open(f)
        print(f"{f}: size={img.size}, mode={img.mode}, format={img.format}")
