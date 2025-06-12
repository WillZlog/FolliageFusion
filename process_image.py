#!/usr/bin/env python3
"""
process_image.py

Called by server_http.py whenever a new JPEG arrives from the Pi.

1) Run a PyTorch MobileNetV2–based “tree detection.” If no tree is found, delete the image and exit.
2) If a tree is found, prompt user once (in the terminal) to input the species.
3) Rename the JPEG to include the species.
4) Ask for ZIP code.
5) Call pipeline.py --image <newPath> --species <species> --zip <ZIP>.
"""

import sys
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

# Your plant/tree keywords
PLANT_KEYWORDS = {
    "plant", "flower", "leaf", "potted", "cactus", "fern", "vegetable",
    "houseplant", "shrub", "mushroom", "carnation", "sunflower", "daisy",
    "dandelion", "orchid", "rose", "tulip", "bonsai",
    # tree‐related terms
    "tree", "oak", "pine", "birch", "maple", "elm", "willow", "cedar",
    "spruce", "sequoia", "redwood", "chestnut", "poplar", "fir", "ash",
    "cypress", "yew", "holly", "almond", "walnut", "linden", "cottonwood",
    "sycamore"
}

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 process_image.py /path/to/image.jpg")
        sys.exit(1)

    orig_path = Path(sys.argv[1])
    if not orig_path.is_file():
        print(f"ERROR: File not found: {orig_path}")
        sys.exit(1)

    print(f"\n▶ Processing '{orig_path.name}' …")

    # 2) Prompt for species
    while True:
        species = input("Enter TREE SPECIES (e.g. 'oak', 'pine'): ").strip().lower()
        if species:
            break
        print(" – Please type a non‐empty species name and press ENTER.")

    # 4) Prompt for ZIP code
    zip_code = input("Enter your 5-digit ZIP code for care location: ").strip()
    if not (zip_code.isdigit() and len(zip_code) == 5):
        print("Error: ZIP code must be exactly 5 digits.")
        sys.exit(1)

    # 5) Call the pipeline
    try:
        subprocess.run(
            ["python3", "pipeline.py",
             "--image", str(orig_path),
             "--species", species,
             "--zip", zip_code],
            check=True
        )
        print(f" ↪ Launched pipeline.py on '{orig_path.name}' (species={species})")
    except subprocess.CalledProcessError as e:
        print(f"❌ pipeline.py failed: {e}")
        sys.exit(1)

    print("✅ Finished process_image.\n")

if __name__ == "__main__":
    main()