from pydicom.valuerep import PersonName
from datetime import datetime
from pydicom.datadict import keyword_for_tag
from pydicom.tag import Tag
from io import BytesIO
import os
import pydicom
import struct
from pydicom.datadict import keyword_for_tag
from pydicom.tag import Tag
from bcolors import bcolors
import struct

"""
no_change_no_pydicom imports ok, recons ok 
no_change imports ok, recon ok 
even_length_change imports ok, recon ok 
smaller_length_change imports with struggle, recon fails
larger_length_change imports failed, recon fails


"""

class RawDicomManager:
    def __init__(self, raw_path):
        self.raw_path = raw_path
        self.start_offset, self.end_offset = find_dicom_in_raw(raw_path)

        if self.start_offset is None or self.end_offset is None:
            raise ValueError("No DICOM data found in RAW file")
        
        with open(raw_path, "rb") as f:
            f.seek(self.start_offset)
            dicom_data = f.read(self.end_offset - self.start_offset)
        self.ds = pydicom.dcmread(BytesIO(dicom_data))
        f.close()

        self.keyword_to_tag = {keyword_for_tag(key) or Tag(key): Tag(key) for key, val in self.ds.to_json_dict().items()}
    
    def viewDicomData(self):
        return print(self.ds)
    
    def editDicomData(self, path:str, new_value:str|int|float):
        res = editDicomData(self.ds, path, new_value, self.keyword_to_tag)
        print(res["message"])
        return res["success"]

    
    def saveAsDCMData(self, output_path):
        self.ds.save_as(output_path,write_like_original=True)
    def saveAsRawDataInPlace(self, output_path):

        original_dicom_size = self.end_offset - self.start_offset
        print(f"DICOM start: {self.start_offset}")
        print(f"DICOM end:   {self.end_offset}")
        print(f"DICOM size:  {original_dicom_size}")

        with open(self.raw_path, "rb") as f:
            raw_bytes = bytearray(f.read())


        original_region = raw_bytes[self.start_offset:self.end_offset]

        print(f"Original embedded region size: {len(original_region)}")

        buffer = BytesIO()
        self.ds.save_as(buffer,write_like_original=True)
        new_dicom_data = buffer.getvalue()
    
        print(f"New DICOM size: {len(new_dicom_data)}")

        if len(new_dicom_data) > original_dicom_size + 16:
            return {
                "success": False,
                "message": "New DICOM too large for in-place replacement"
            }


        if len(new_dicom_data) < original_dicom_size:
            print(f"New DICOM is smaller than original by {original_dicom_size - len(new_dicom_data)} bytes. Padding with zeros.")
            new_dicom_data = new_dicom_data.ljust(original_dicom_size, b"\x00")

        # If slightly larger but within tolerance, we still enforce fixed slot
        if len(new_dicom_data) > original_dicom_size:
            print(f"New DICOM is larger than original by {len(new_dicom_data) - original_dicom_size} bytes, but within tolerance. Truncating to fit.")
            new_dicom_data = new_dicom_data[:original_dicom_size]


        raw_bytes[self.start_offset:self.end_offset] = new_dicom_data


        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, "edited.rawmdu")

        with open(output_path, "wb") as f:
            f.write(raw_bytes)

        print(f"Saved updated RAW file to: {output_path}")

        return {
            "success": True,
            "output_path": output_path
        }

    def __str__(self):
        return self.viewDicomData()


def find_first_dicm_offset(raw_path: str) -> int:
    with open(raw_path, "rb") as f:
        chunk_size = 1024 * 1024 # 1 MB
        overlap = b""
        pos = 0
        
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            data = overlap + chunk
            i = data.find(b"DICM")
            
            if i != -1:
                return pos + i - len(overlap)
            
            overlap = data[-3:]
            pos += chunk_size

    return -1

def find_dicom_in_raw(path):

    VALID_VR = {
        b'AE', b'AS', b'AT', b'CS', b'DA', b'DS', b'DT',
        b'FD', b'FL', b'IS', b'LO', b'LT', b'OB', b'OD',
        b'OF', b'OL', b'OW', b'PN', b'SH', b'SL', b'SQ',
        b'SS', b'ST', b'TM', b'UC', b'UI', b'UL', b'UN',
        b'UR', b'US', b'UT'
    }

    MAX_ELSCINT_GAP = 10* 1024 * 1024  # 10 MB

    CHUNK_SIZE = 1024 * 1024  # 1 MB

    with open(path, "rb") as f:

        dicm_offset = find_first_dicm_offset(path)

        if dicm_offset is None:
            raise ValueError("No DICM marker found")

        # Real DICOM starts 128 bytes before DICM
        start = max(0, dicm_offset - 128)

        f.seek(start)

        print(f"Starting scan at {start}")

        last_valid_pos = start
        last_elscint_pos = start

        while True:

            chunk_start = f.tell()

            chunk = f.read(CHUNK_SIZE)

            if not chunk:
                print("Reached EOF")
                break

            chunk_len = len(chunk)

            i = 0

            while i < chunk_len - 8:

                absolute_pos = chunk_start + i

                if chunk[i:i+8] == b'ELSCINT':

                    last_elscint_pos = absolute_pos
                    last_valid_pos = absolute_pos


                vr = chunk[i+4:i+6]

                if vr in VALID_VR:
                    last_valid_pos = absolute_pos

                if (absolute_pos - last_elscint_pos) > MAX_ELSCINT_GAP:

                    print(f"No ELSCINT detected for {MAX_ELSCINT_GAP} bytes.")
                    print(f"Stopping at {last_valid_pos}")

                    return (start, last_valid_pos)

                i += 1

        return (start, last_valid_pos)


from pydicom.valuerep import PersonName


def editDicomData(ds, path: str, new_value: str | int | float, keyword_to_tag):

    keys = path.split(".")
    current_level = ds
    vr = None

    for key in keys[:-1]:
        tagKey = keyword_to_tag.get(key, key)
        if isinstance(tagKey, str) and tagKey.isdigit():
            current_level = current_level.value[int(tagKey)]
        else:
            if tagKey not in current_level:
                return {"success": False,"message": f"{bcolors.FAIL}Path not found: {path}{bcolors.END}" }

            current_level = current_level[tagKey]
            vr = current_level.VR or vr

    last_key = keyword_to_tag.get(keys[-1], keys[-1])


    if isinstance(last_key, str) and last_key.isdigit():
        original_value = str(current_level.value[int(last_key)])
        validated_res = validate_vr(vr, new_value)

        if validated_res["success"] is False:
            return validated_res

        validated_value = str(validated_res["value"])

        original_len = len(original_value.encode("utf-8"))
        new_len = len(validated_value.encode("utf-8"))

        # This causes shifting of all downstream binary data and breaks RAW reconstruction, so we reject it outright
        if new_len > original_len:
            return {
                "success": False,
                "message":
                    f"{bcolors.FAIL}New value exceeds allowed byte length.{bcolors.END}\n"
                    f"Original max length: {original_len} bytes\n"
                    f"New value length: {new_len} bytes\n\n"
                    f"{bcolors.FAIL}Variable-length expansion shifts downstream binary "
                    f"data and causes RAW reconstruction failure.{bcolors.END}"
            }


        # Local padding to preserve byte length
        padded_value = pad_value_for_vr(vr,validated_value, original_len)
        current_level.value[int(last_key)] = padded_value
        return {
            "success": True,
            "message": f"{bcolors.OKGREEN}Updated {path} (original={original_len} bytes, new={new_len} bytes){bcolors.END}"
        }
    else:
        if last_key not in current_level:
            return {
                "success": False,
                "message": f"{bcolors.FAIL}Path not found: {path}{bcolors.END}"
            }

        element = current_level[last_key]
        vr = element.VR or vr

        validated_res = validate_vr(vr, new_value)

        if validated_res["success"] is False:
            return validated_res

        validated_value = str(validated_res["value"])
        original_value = str(element.value)


        original_len = len(original_value.encode("utf-8"))
        new_len = len(validated_value.encode("utf-8"))

        if new_len > original_len:
            return {
                "success": False,
                "message":
                    f"{bcolors.FAIL}New value exceeds allowed byte length.{bcolors.END}\n"
                    f"Original max length: {original_len} bytes\n"
                    f"New value length: {new_len} bytes\n"
                    f"{bcolors.FAIL}Expanding embedded DICOM fields changes internal "
                    f"binary structure and causes RAW reconstruction failure.{bcolors.END}"
            }

        padded_value = pad_value_for_vr(vr, validated_value, original_len)

        if vr == "PN":
            element.value = PersonName(padded_value)
        else:
            element.value = padded_value

        return {
            "success": True,
            "message":
                f"{bcolors.OKGREEN}Updated {path} "
                f"(original={original_len} bytes, "
                f"new={new_len} bytes){bcolors.END}"
        }


def pad_value_for_vr(vr, value: str, target_len: int):

    encoded = value.encode("utf-8")
    padding_needed = target_len - len(encoded)
    if padding_needed <= 0:
        return value
    
    # UI uses NULL padding
    if vr == "UI":
        return value + ("\0" * padding_needed)

    # Text VRs typically use SPACE padding
    elif vr in ["PN", "LO", "SH", "ST", "LT", "UT", "CS", "AE"]:
        return value + (" " * padding_needed)

    return value + (" " * padding_needed)

def validate_vr(vr, value):
    try:
        if vr in ["LO", "SH", "ST", "LT", "UT", "CS", "AE"]:
            return {"success": True, "value": str(value)}

        elif vr == "PN":
            return {"success": True, "value": PersonName(str(value))}

        elif vr in ["DA"]:  # Date YYYYMMDD
            if isinstance(value, str):
                datetime.strptime(value, "%Y%m%d")
                return {"success": True, "value": value}
            return {"success": False, "message": "Incorrect date format, expected YYYYMMDD"}

        elif vr in ["TM"]:  # Time HHMMSS
            if isinstance(value, str):
                datetime.strptime(value.split(".")[0], "%H%M%S")
                return {"success": True, "value": value}
            return {"success": False, "message": "Incorrect time format, expected HHMMSS or HHMMSS.FFFFFF"}

        elif vr in ["UI"]:  # UID
            return {"success": True, "value": str(value)}

        elif vr in ["IS"]:  # Integer String
            return {"success": True, "value": str(int(value))}

        elif vr in ["DS"]:  # Decimal String
            return {"success": True, "value": str(float(value))}

        elif vr in ["US", "UL", "SS", "SL"]:
            return {"success": True, "value": int(value)}   

        elif vr in ["FL", "FD"]:
            return {"success": True, "value": float(value)}

        elif vr in ["OB", "OW", "UN"]:
            if isinstance(value, (bytes, bytearray)):
                return {"success": True, "value": value}
            return {"success": False, "message": "Invalid value for VR 'OB', 'OW', or 'UN'"}

        elif vr == "SQ":
            # Sequences must be list of datasets
            return {"success": True, "value": value} if isinstance(value, list) else {"success": False, "message": "Invalid value for VR 'SQ'"}

        else:
            # fallback: allow but cast to string
            return {"success": True, "value": str(value)}

    except Exception as e:
        return {"success": False, "message": f"An error occurred while validating the value: {e}"}