# move_all_data.py - Save in FinalProject folder and run
import os
import shutil
import pandas as pd
from pathlib import Path

print("🚚 MOVING ALL DATA TO FinalProject/data/")
print("=" * 60)

# Define ALL possible locations where data might be
data_locations = [
    'data/',  # Project root (target)
    'crawlers/data/',  # Crawlers folder
    '.venv/data/',  # Virtual environment
    'crawlers/crawlers/data/',  # Nested crawlers
    'src/data/',  # Source folder
    'app/data/',  # App folder
]

# Target directory (where we want everything)
TARGET_DIR = 'data/'
os.makedirs(TARGET_DIR, exist_ok=True)

print(f"🎯 Target directory: {os.path.abspath(TARGET_DIR)}")
print()

# Find ALL CSV files in the entire project
all_csv_files = []
for root, dirs, files in os.walk('.'):
    # Skip virtual environments and hidden folders
    if '.venv' in root or '__pycache__' in root or '.git' in root:
        continue

    for file in files:
        if file.endswith('.csv'):
            full_path = os.path.join(root, file)
            all_csv_files.append(full_path)

print(f"🔍 Found {len(all_csv_files)} CSV files in project:")
for csv in all_csv_files:
    print(f"  📄 {csv}")

print(f"\n📦 MOVING MAIN DATA FILES...")

# Important files (these should be in FinalProject/data/)
main_files = ['amazon_products.csv', 'jd_products.csv', 'all_products.csv', 'database_export.csv']

for main_file in main_files:
    print(f"\n📄 Processing {main_file}:")

    # Find all instances of this file
    found_copies = []
    for csv_path in all_csv_files:
        if csv_path.endswith(main_file):
            found_copies.append(csv_path)

    if found_copies:
        print(f"   Found {len(found_copies)} copies:")

        # Merge all copies into one
        all_data = []
        for copy_path in found_copies:
            try:
                df = pd.read_csv(copy_path)
                print(f"   • {copy_path}: {len(df)} rows")
                all_data.append(df)
            except Exception as e:
                print(f"   • {copy_path}: Error reading - {e}")

        if all_data:
            # Merge all data
            merged_df = pd.concat(all_data, ignore_index=True)

            # Remove duplicates (keep newest based on timestamp if available)
            if 'crawl_timestamp' in merged_df.columns:
                merged_df = merged_df.sort_values('crawl_timestamp', ascending=False)
                merged_df = merged_df.drop_duplicates(
                    subset=['product_id', 'platform'] if all(
                        c in merged_df.columns for c in ['product_id', 'platform']) else None,
                    keep='first'
                )

            # Save to target location
            target_path = os.path.join(TARGET_DIR, main_file)
            merged_df.to_csv(target_path, index=False, encoding='utf-8-sig')

            print(f"   ✅ MERGED: {len(merged_df)} rows saved to {target_path}")

            # Optional: Delete old copies (uncomment if you want)
            # for copy_path in found_copies:
            #     if copy_path != target_path:
            #         os.remove(copy_path)
            #         print(f"   🗑️ Deleted: {copy_path}")
    else:
        print(f"   ⚠️ File not found anywhere")

print(f"\n📦 MOVING OTHER CSV FILES (backups, exports, etc.)...")

# Move all other CSV files to an archive folder
archive_dir = os.path.join(TARGET_DIR, 'archive')
os.makedirs(archive_dir, exist_ok=True)

other_files_moved = 0
for csv_path in all_csv_files:
    filename = os.path.basename(csv_path)

    # Skip if already in target or if it's a main file we already processed
    if TARGET_DIR in csv_path or filename in main_files:
        continue

    try:
        # Move to archive
        archive_path = os.path.join(archive_dir, filename)

        # If file already exists in archive, rename it
        counter = 1
        while os.path.exists(archive_path):
            name, ext = os.path.splitext(filename)
            archive_path = os.path.join(archive_dir, f"{name}_{counter}{ext}")
            counter += 1

        shutil.move(csv_path, archive_path)
        print(f"   📦 Archived: {csv_path} → {archive_path}")
        other_files_moved += 1

    except Exception as e:
        print(f"   ❌ Failed to move {csv_path}: {e}")

print(f"\n🎯 FINAL RESULT:")
print(f"   Main data files: {len(main_files)} files in {os.path.abspath(TARGET_DIR)}")
print(f"   Archived files: {other_files_moved} files in {os.path.abspath(archive_dir)}")

# Show final directory structure
print(f"\n📁 FINAL DATA FOLDER STRUCTURE:")
for item in os.listdir(TARGET_DIR):
    item_path = os.path.join(TARGET_DIR, item)
    if os.path.isfile(item_path):
        size = os.path.getsize(item_path)
        print(f"   📄 {item} ({size} bytes)")
    elif os.path.isdir(item_path):
        file_count = len([f for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))])
        print(f"   📁 {item}/ ({file_count} files)")