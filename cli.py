import json
import os
from RawDicomManager import RawDicomManager

class bcolors:
    HEADER = '\x1B[1m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    ITALIC = '\033[3m'


# Build command: python -m PyInstaller --onefile --hidden-import=pydicom cli.py
"""

NOTE:
- NEED TO DESCRIBE HOW THE KEYS WORK IN THE EDITING FUNCTION (BOTH SINGLE AND JSON)
    THIS INVOLVES REPLACING SPACES WITH CAMEL NOTATION, AND ALSO HOW TO INDEX INTO SEQUENCES (E.G. IMAGE TYPE.1)
- ALSO NEED TO DESCRIBE HOW THE JSON FILE SHOULD BE STRUCTURED FOR BATCH EDITING
"""

msg = f"""
    {bcolors.HEADER}📘 How to Reference and Edit DICOM Fields{bcolors.END}

    When viewing the DICOM data, field names may appear {bcolors.BOLD}human-readable{bcolors.END} (e.g., {bcolors.ITALIC}Patient's Name{bcolors.END}).
    However, when editing values, you must use the {bcolors.BOLD}DICOM keyword format{bcolors.END}.

    ---
    {bcolors.HEADER} 🔑 Key Formatting Rules{bcolors.END}

    * Remove spaces and punctuation
    * Use the exact **DICOM keyword** (no apostrophes)

    {bcolors.HEADER} Examples:{bcolors.END}

    * {bcolors.BOLD}Displayed:{bcolors.END} Patient's Name → {bcolors.BOLD}Use:{bcolors.END} `PatientName`
    * {bcolors.BOLD}Displayed:{bcolors.END} Referring Physician's Name → {bcolors.BOLD}Use:{bcolors.END} `ReferringPhysicianName`
    * {bcolors.BOLD}Displayed:{bcolors.END} Image Type → {bcolors.BOLD}Use:{bcolors.END} `ImageType`

    ---
    {bcolors.HEADER} 🧱 Understanding Data Structures{bcolors.END}

    DICOM values can have different structures. Your edit path depends on the structure type.
    ---

    {bcolors.HEADER} 1. Primary Value{bcolors.END}

    Single value stored in a list

    SpecificCharacterSet: ['ISO_IR 100']

    ✅ Path: SpecificCharacterSet

    ---
    {bcolors.HEADER} 2. Array of Values{bcolors.END}

    Multiple values in a list

    ImageType: ['ORIGINAL', 'PRIMARY', 'AXIAL', 'HELICAL']

    ✅ Paths:
        ImageType.0
        ImageType.1
        ImageType.2
        ImageType.3

    ---

    {bcolors.HEADER} 3. Person Name (PN){bcolors.END}

    Structured object with subfields

    ReferringPhysicianName: [{{ Alphabetic: 'ReferringPhysField' }}]
    ✅ Path: ReferringPhysicianName
    ---
    {bcolors.HEADER} 4. Nested Sequences (SQ){bcolors.END}

        Lists of nested datasets

        ReferencedImageSequence:
        [
        {{
            ReferencedSOPClassUID: ['1.2...'],
            ReferencedSOPInstanceUID: ['1.3...']
        }},
        ...
        ]

    ✅ Paths:
        ReferencedImageSequence.0.ReferencedSOPClassUID
        ReferencedImageSequence.1.ReferencedSOPInstanceUID

    ---
    {bcolors.HEADER} 🧭 General Path Rules{bcolors.END}

    * Use `.` (dot) to separate levels
    * Use {bcolors.BOLD}indices{bcolors.END} (`0`, `1`, etc.) to access list elements
    * Always drill down to the {bcolors.BOLD}actual value{bcolors.END}

    {bcolors.HEADER} Pattern:{bcolors.END}
        <Key>.<index>.<optional nested keys>

    {bcolors.HEADER} ✅ Examples{bcolors.END}

    PatientName
    ImageType.1
    ReferringPhysicianName
    ReferencedImageSequence.0.ReferencedSOPClassUID
    ---
    {bcolors.HEADER} ⚠️ Important Notes{bcolors.END}

    * Paths are {bcolors.BOLD}case-sensitive{bcolors.END}
    * If a path is invalid or the value does not match the expected format (VR), the edit will fail
    * Always include the final `.0` when the value is stored as a list
    ---
    {bcolors.HEADER} 💡 Tip{bcolors.END}

    If unsure about a path:
    1. Use the "View DICOM" option
    2. Follow the structure exactly as shown
    3. Convert field names to keyword format (no spaces/apostrophes)
    ---
    This system ensures precise editing of deeply nested DICOM data while maintaining file integrity.


    📄 JSON Batch Edit Format

        You can apply multiple edits at once by providing a JSON file.

        ✅ Expected Format

        The JSON file must be a dictionary (object) where:

        Key = DICOM path
        Value = new value to assign
        Example:
        {{
        "PatientName": "Anonymous",
        "ImageType.1": "MODIFIED",
        "ReferringPhysicianName": "Dr^Hidden",
        "ReferencedImageSequence.0.ReferencedSOPInstanceUID": "1.2.3.4.5"
        }}

"""

def run_cli():
    print("=== RAW DICOM Editor ===")

    raw_path = None
    while not raw_path:
        raw_path = input("Enter path to RAW file (include the file in the path): ").strip()
        #raw_path = r"C:\Users\320308966\Documents\RawDataManager\1.3.46.670589.61.128.7.2026020311233319822097493910003.rawmdu"

        if not os.path.exists(raw_path):
            print("File not found.")
            raw_path = None
            continue
        
        try:
            manager = RawDicomManager(raw_path)
        except Exception as e:
            print(f"Failed to load RAW file: {e}")
            raw_path = None

    print(msg)
    print("\n\nDICOM successfully loaded.\n")

    while True:
        print("\nOptions (type the number):")
        print("1. View DICOM")
        print("2. Edit a value")
        print("3. Apply edits from JSON")
        print("4. Save as RAW")
        print("5. Save as DCM")
        print("6. Exit")

        choice = input("Select option: ").strip()

        # ---- VIEW ----
        if choice == "1":
            manager.viewDicomData()

        # ---- SINGLE EDIT ----
        elif choice == "2":
            path = input("Enter path (e.g. ImageType.1): ").strip()
            value = input("Enter new value: ").strip()

            manager.editDicomData(path, value)

        # ---- JSON EDIT ----
        elif choice == "3":
            json_path = input("Enter JSON file path: ").strip()

            if not os.path.exists(json_path):
                print("JSON file not found.")
                continue

            with open(json_path, "r") as f:
                edits = json.load(f)
            if not isinstance(edits, dict):
                print("Invalid JSON format. Expected a dictionary of path:value pairs.")
                continue

            for path, value in edits.items():
                success = manager.editDicomData(path, value)
                print(f"{path} → {'OK' if success else 'FAILED'}")

        # ---- SAVE RAW ----
        elif choice == "4":
            output_path = input("Output RAW file path: ").strip()
            manager.saveAsRawData(output_path)
            print("Saved RAW file.")

        # ---- SAVE DCM ----
        elif choice == "5":
            output_path = input("Output DCM file path: ").strip()
            manager.saveAsDCMData(output_path)
            print("Saved DICOM file.")

        elif choice == "6":
            print("Exiting.")
            break

        else:
            print("Invalid option.")
    
if __name__ == "__main__":
    run_cli()