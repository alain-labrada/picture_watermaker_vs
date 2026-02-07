# Picture Watermark Tool

Automatically add location and year watermarks to your photos based on EXIF data and GPS coordinates. Works with photos taken on both **iPhone** and **Samsung Galaxy** devices.

## Features

- Supports photos from both iPhone and Samsung Galaxy (handles different EXIF metadata formats)
- Extracts year from photo EXIF data
- Extracts GPS coordinates and converts them to city names
- Matches photos to locations from your `locations.txt` file based on year and proximity
- Falls back to GPS city name when the closest location from file is more than 100 km away
- Preserves correct photo orientation (portrait photos stay portrait after watermarking)
- Adds watermarks with white text, black outline, and shadow for readability
- Supports JPG, PNG, TIFF, and HEIC/HEIF image formats (HEIC files are converted to JPG on output)

## Device Compatibility

The tool handles differences in how iPhone and Samsung store photo metadata:

- **EXIF extraction**: Uses Pillow's public `getexif()` API with IFD sub-access, with a fallback to `_getexif()` for older formats
- **GPS coordinates**: Handles IFDRational objects (iPhone), (numerator, denominator) tuples (Samsung), and plain float values
- **Date fields**: Handles standard strings, bytes-encoded values (some Samsung models), null-byte padding, and timezone offsets
- **GPS reference values**: Handles both string and bytes-encoded N/S/E/W references
- **Photo orientation**: Applies EXIF orientation transform so portrait photos are not saved as landscape

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Basic usage with input folder:
```bash
python watermark_photos.py ~/Pictures/vacation
```

2. Specify locations file:
```bash
python watermark_photos.py -l locations.txt ~/Pictures/vacation
```

3. Specify both locations file and output folder:
```bash
python watermark_photos.py -l locations.txt -o ~/Pictures/watermarked ~/Pictures/vacation
```

### Command-line Options

- `input_folder` - (Required) Folder containing photos to watermark
- `-l, --locations` - Locations CSV file (default: locations.txt)
- `-o, --output` - Output folder for watermarked photos (default: watermarked_photos)
- `-h, --help` - Show help message

### Examples

```bash
# Use default locations.txt and output to watermarked_photos/
python watermark_photos.py input_photos

# Use custom locations file
python watermark_photos.py -l my_locations.txt ~/Pictures/vacation

# Specify everything
python watermark_photos.py -l locations.txt -o ~/Desktop/output ~/Pictures/vacation
```

## locations.txt Format

```
2025, Blue Ridge
2025, Roma
2025, Venezia
2025, Pisa
```

## How It Works

1. Reads all images from the input folder
2. Extracts the year the photo was taken from EXIF data
3. Extracts GPS coordinates from EXIF data
4. Converts coordinates to city names using reverse geocoding
5. Finds the closest matching location from `locations.txt` based on the year
6. If the matched location is more than 100 km away, uses the city name from GPS instead
7. Corrects photo orientation based on EXIF data
8. Adds a watermark label in the bottom left corner with the format: "YEAR, LOCATION"
9. Saves the watermarked image (HEIC/HEIF files are converted to JPG)

## Requirements

- Photos must have EXIF data with date information
- Photos with GPS coordinates will get more accurate location matching
- Internet connection required for geocoding (converting coordinates to city names)
