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

import struct


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
        self.ds.save_as(output_path)

    def saveAsRawData(self, output_path):

        original_dicom_size = self.end_offset - self.start_offset

        print(f"DICOM start: {self.start_offset}")
        print(f"DICOM end:   {self.end_offset}")
        print(f"DICOM size:  {original_dicom_size}")

        buffer = BytesIO()
        self.ds.save_as(buffer,write_like_original=True)
        new_dicom_data = buffer.getvalue()

        print(f"New DICOM size: {len(new_dicom_data)}")

        if len(new_dicom_data) > original_dicom_size:
            return {"success": False,"message": "Failed to save as RAW data",}


        padded_dicom = new_dicom_data.ljust(original_dicom_size,b"\x00")

        with open(self.raw_path, "rb") as f:
            raw_bytes = f.read()

        new_raw = (raw_bytes[:self.start_offset] + padded_dicom + raw_bytes[self.end_offset:])
        f.close()

        # -----------------------------------------
        # Output handling
        # -----------------------------------------

        if os.path.isdir(output_path):
            output_path = os.path.join(output_path,"edited.rawmdu")

        with open(output_path, "wb") as f:
            f.write(new_raw)
        f.close()

        print(f"Saved updated RAW file to: {output_path}")
        return {"success": True,"output_path": output_path,}
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

def editDicomData(ds,path:str,new_value:str|int|float, keyword_to_tag):
    keys = path.split(".")
    current_level = ds
    vr = None
    
    # Exclude last key
    for key in keys[:-1]:
        tagKey = keyword_to_tag.get(key, key)
        if type(tagKey) == str and tagKey.isdigit():
            current_level = current_level.value[int(tagKey)]
        else:
            # tagKey is of type Tag
            if tagKey not in current_level:
                return {"success":False, "message": f"Path not found: {path}"}
            current_level = current_level[tagKey]
            vr = current_level.VR or vr
    
     # Check if the last key is a subkey (like 'Alphabetic' in a Person Name)
    last_key = keyword_to_tag.get(keys[-1], keys[-1])
    

    if type(last_key) == str and last_key.isdigit():
        validated_res = validate_vr(vr, new_value)
        if validated_res["success"] is False:
            return {"success":False, "message": validated_res["message"]}
        current_level.value[int(last_key)] = validated_res["value"]
        return {"success":True, "message": f"Updated {path} to {validated_res['value']}"}
    else:
        # last_key is of type Tag
        if last_key not in current_level:
                return {"success":False, "message": f"Path not found: {path}"}
        vr = current_level[last_key].VR or vr
        validated_res = validate_vr(vr, new_value)
        if validated_res["success"] is False:
            return {"success":False, "message": validated_res["message"]}
        current_level[last_key].value = validated_res["value"]
        return {"success":True, "message": f"Updated {path} to {validated_res['value']}"}



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