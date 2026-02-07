import os
import csv
import argparse
import ssl
import certifi
from PIL import Image, ImageDraw, ImageFont, ExifTags
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import time
import pillow_heif

# Register HEIF opener for HEIC support
pillow_heif.register_heif_opener()

# Create SSL context for geocoding
try:
    ctx = ssl.create_default_context(cafile=certifi.where())
except:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

def get_exif_data(image_path):
    """Extract EXIF data from image."""
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        
        if not exif_data:
            return None, None, None
        
        exif = {
            ExifTags.TAGS[k]: v
            for k, v in exif_data.items()
            if k in ExifTags.TAGS
        }
        
        return exif, image
    except Exception:
        return None, None

def get_year_from_exif(exif):
    """Extract year from EXIF data."""
    if not exif:
        return None
    
    # Try different date fields
    date_fields = ['DateTimeOriginal', 'DateTime', 'DateTimeDigitized']
    
    for field in date_fields:
        if field in exif:
            try:
                date_str = exif[field]
                # Format is usually "YYYY:MM:DD HH:MM:SS"
                year = int(date_str.split(':')[0])
                return year
            except Exception:
                continue
    
    return None

def get_gps_coordinates(exif):
    """Extract GPS coordinates from EXIF data."""
    if not exif or 'GPSInfo' not in exif:
        return None, None
    
    gps_info = exif['GPSInfo']
    
    def convert_to_degrees(value):
        """Convert GPS coordinates to degrees."""
        d, m, s = value
        return d + (m / 60.0) + (s / 3600.0)
    
    try:
        gps_latitude = gps_info.get(2)
        gps_latitude_ref = gps_info.get(1)
        gps_longitude = gps_info.get(4)
        gps_longitude_ref = gps_info.get(3)
        
        if gps_latitude and gps_longitude:
            lat = convert_to_degrees(gps_latitude)
            if gps_latitude_ref == 'S':
                lat = -lat
            
            lon = convert_to_degrees(gps_longitude)
            if gps_longitude_ref == 'W':
                lon = -lon
            
            return lat, lon
    except Exception:
        pass
    
    return None, None

def get_city_from_coordinates(lat, lon):
    """Get city name from GPS coordinates using reverse geocoding."""
    try:
        geolocator = Nominatim(user_agent="photo_watermark_app", timeout=10, ssl_context=ctx)
        time.sleep(1.5)  # Be respectful to the API
        location = geolocator.reverse(f"{lat}, {lon}", language='en', exactly_one=True)
        
        if location and location.raw.get('address'):
            address = location.raw['address']
            # Try to get city from various fields
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or
                   address.get('county') or
                   address.get('state'))
            return city
        else:
            # Try one more time with a longer delay
            time.sleep(2)
            location = geolocator.reverse(f"{lat}, {lon}", language='en')
            if location and location.raw.get('address'):
                address = location.raw['address']
                city = (address.get('city') or 
                       address.get('town') or 
                       address.get('village') or 
                       address.get('municipality') or
                       address.get('county') or
                       address.get('state'))
                return city
    except Exception as e:
        print(f"  ⚠ Geocoding error: {e}")
    
    return None

def load_locations(locations_file):
    """Load locations from CSV file."""
    locations = []
    try:
        with open(locations_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    year = int(row[0].strip())
                    location = row[1].strip()
                    locations.append((year, location))
    except Exception:
        pass
    
    return locations

def get_coordinates_for_city(city_name):
    """Get coordinates for a city name."""
    try:
        geolocator = Nominatim(user_agent="photo_watermark_app", timeout=10, ssl_context=ctx)
        time.sleep(1.5)
        location = geolocator.geocode(city_name)
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass
    
    return None, None

def find_closest_location(year, photo_city, photo_coords, locations, verbose=False):
    """Find the closest location from locations.txt based on year and proximity."""
    if not year or not locations:
        return None
    
    # Filter locations by year
    year_matches = [loc for yr, loc in locations if yr == year]
    
    if not year_matches:
        return None
    
    # If only one match, return it
    if len(year_matches) == 1:
        if verbose:
            print(f"  → Only one location for {year}: {year_matches[0]}")
        return year_matches[0]
    
    # If we have photo coordinates, find the closest location
    if photo_coords and photo_coords[0] is not None:
        photo_lat, photo_lon = photo_coords
        min_distance = float('inf')
        closest_location = None
        
        if verbose:
            print(f"  → Checking {len(year_matches)} locations for proximity...")
        
        for location_name in year_matches:
            loc_coords = get_coordinates_for_city(location_name)
            if loc_coords and loc_coords[0] is not None:
                distance = geodesic(photo_coords, loc_coords).kilometers
                if verbose:
                    print(f"     {location_name}: {distance:.1f} km")
                if distance < min_distance:
                    min_distance = distance
                    closest_location = location_name
        
        if closest_location:
            if verbose:
                print(f"  → Closest: {closest_location} ({min_distance:.1f} km)")
            return closest_location
    
    # If we can't determine by distance, return the first match
    if verbose:
        print(f"  → Using first match for {year}: {year_matches[0]}")
    return year_matches[0]

def add_watermark(image, text, position='bottom-left'):
    """Add watermark text with white letters, black outline, and shadow."""
    draw = ImageDraw.Draw(image)
    
    # Try to use a nice font, fall back to default if not available
    try:
        font_size = int(image.height * 0.04)  # 4% of image height
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        except:
            font = ImageFont.load_default()
    
    # Get text bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # Calculate position
    margin = int(image.width * 0.02)  # 2% margin
    
    if position == 'bottom-left':
        x = margin
        y = image.height - text_height - margin - 10
    else:  # default to bottom-left
        x = margin
        y = image.height - text_height - margin - 10
    
    # Draw shadow (offset)
    shadow_offset = 5
    draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill='black')
    
    # Draw outline (black)
    outline_range = 4
    for adj_x in range(-outline_range, outline_range + 1):
        for adj_y in range(-outline_range, outline_range + 1):
            if adj_x != 0 or adj_y != 0:
                draw.text((x + adj_x, y + adj_y), text, font=font, fill='black')
    
    # Draw main text (white)
    draw.text((x, y), text, font=font, fill='white')
    
    return image

def process_images(input_folder, output_folder, locations_file):
    """Process all images in the input folder."""
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"✓ Created output folder: {output_folder}\n")
    
    locations = load_locations(locations_file)
    print(f"✓ Loaded {len(locations)} location entries from {locations_file}\n")
    
    # Supported image formats
    image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.heif')
    
    # Find all image files
    image_files = [f for f in os.listdir(input_folder) if f.lower().endswith(image_extensions)]
    
    if not image_files:
        print(f"⚠ No image files found in {input_folder}")
        print(f"  Looking for: {', '.join(image_extensions)}")
        return
    
    print(f"✓ Found {len(image_files)} image(s) to process\n")
    print("=" * 70)
    
    # Track statistics
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    for idx, filename in enumerate(image_files, 1):
        image_path = os.path.join(input_folder, filename)
        print(f"\n[{idx}/{len(image_files)}] Processing: {filename}")
        print("-" * 70)
        
        try:
            # Get EXIF data
            exif, image = get_exif_data(image_path)
            
            if not exif:
                print(f"  ✗ No EXIF data found - SKIPPED")
                skipped_count += 1
                continue
            
            print(f"  ✓ EXIF data extracted")
            
            # Extract year
            year = get_year_from_exif(exif)
            if year:
                print(f"  ✓ Year extracted: {year}")
            else:
                print(f"  ✗ Could not extract year - SKIPPED")
                skipped_count += 1
                continue
            
            # Extract GPS coordinates
            lat, lon = get_gps_coordinates(exif)
            
            if lat and lon:
                print(f"  ✓ GPS coordinates found: {lat:.4f}, {lon:.4f}")
                
                # Get city from coordinates
                city = get_city_from_coordinates(lat, lon)
                if city:
                    print(f"  ✓ City from GPS: {city}")
                else:
                    print(f"  ⚠ Could not resolve city name from GPS")
            else:
                print(f"  ⚠ No GPS coordinates in EXIF data")
                city = None
            
            # Try to find matching location from locations.txt
            matched_location = None
            if lat and lon:
                matched_location = find_closest_location(year, city, (lat, lon), locations, verbose=True)
            
            # Determine label: prefer matched location from file, fallback to GPS city
            if matched_location:
                watermark_text = f"{year}, {matched_location}"
                print(f"  ✓ Adding watermark: '{watermark_text}' (year + location from file)")
            elif city:
                watermark_text = f"{year}, {city}"
                print(f"  ✓ Adding watermark: '{watermark_text}' (year + city from metadata)")
            else:
                watermark_text = f"{year}"
                print(f"  ✓ Adding watermark: '{watermark_text}' (year only, no location found)")
            
            # Add watermark
            watermarked_image = add_watermark(image, watermark_text)
            
            # Save the watermarked image
            # Convert HEIC to JPG for output compatibility
            output_filename = filename
            if filename.lower().endswith(('.heic', '.heif')):
                output_filename = os.path.splitext(filename)[0] + '.jpg'
                watermarked_image = watermarked_image.convert('RGB')
            
            output_path = os.path.join(output_folder, output_filename)
            watermarked_image.save(output_path, quality=95)
            
            print(f"  ✓ SUCCESS - Saved to: {output_path}")
            success_count += 1
            
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed_count += 1
            continue
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total images found:      {len(image_files)}")
    print(f"Successfully processed:  {success_count} ✓")
    if skipped_count > 0:
        print(f"Skipped (missing data):  {skipped_count} ⚠")
    if failed_count > 0:
        print(f"Failed (errors):         {failed_count} ✗")
    print("=" * 70)

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Add location and year watermarks to photos based on EXIF data.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s ~/Pictures/vacation
  %(prog)s -l locations.txt ~/Pictures/vacation
  %(prog)s -l locations.txt -o output_folder ~/Pictures/vacation
        '''
    )
    
    parser.add_argument(
        'input_folder',
        help='Folder containing photos to watermark'
    )
    
    parser.add_argument(
        '-o', '--output',
        dest='output_folder',
        default='watermarked_photos',
        help='Output folder for watermarked photos (default: watermarked_photos)'
    )
    
    parser.add_argument(
        '-l', '--locations',
        dest='locations_file',
        default='locations.txt',
        help='CSV file with year and location data (default: locations.txt)'
    )
    
    args = parser.parse_args()
    
    # Expand user path (e.g., ~/)
    input_folder = os.path.expanduser(args.input_folder)
    output_folder = os.path.expanduser(args.output_folder)
    locations_file = os.path.expanduser(args.locations_file)
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' not found.")
        return 1
    
    if not os.path.exists(locations_file):
        print(f"Error: Locations file '{locations_file}' not found.")
        return 1
    
    print(f"Input folder: {input_folder}")
    print(f"Output folder: {output_folder}")
    print(f"Locations file: {locations_file}")
    print("\nStarting photo watermarking process...")
    
    process_images(input_folder, output_folder, locations_file)
    print("\nProcessing complete!")
    return 0

if __name__ == "__main__":
    main()
