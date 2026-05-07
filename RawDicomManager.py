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


class RawDicomManager:
    def __init__(self, raw_path):
        self.raw_path = raw_path
        res= readRawAndExtractDicom(raw_path)
        if not res["success"]:
            raise ValueError(res["message"])
        self.ds = res["data"]

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
        ds = pydicom.dcmread(self.raw_path, force=True)

        if (0x01f7, 0x10cc) not in ds:
            raise ValueError("ChessDataSet not found")

        elem = ds[0x01f710cc]
        original_value = elem.value

        # Serialize new DICOM
        buffer = BytesIO()
        self.ds.save_as(buffer)
        dicom_data = buffer.getvalue()

        res = getRAWOffset(self.raw_path)
        if not res["success"]:
            return res  
        dicom_offset = res["data"]

        prefix = original_value[:dicom_offset]
        new_value = prefix + dicom_data

        if len(new_value) > len(original_value):
            raise ValueError("New DICOM larger than original — cannot safely overwrite")

        new_value = new_value.ljust(len(original_value), b"\x00")

        elem.value = new_value


        if os.path.isdir(output_path):
            output_path = os.path.join(output_path, "edited.rawmdu")
        ds.save_as(output_path)
        print(f"Saved new RAW file with updated DICOM at {output_path}")
    def __str__(self):
        return self.viewDicomData()


def getChessDataSet(rawPath: str):
    try:
        ds = pydicom.dcmread(rawPath, defer_size="1KB", force=True)
        
        if (0x01f7, 0x10cc) in ds:
            ChessDataSet = ds[0x01f710cc]
            return {"data": ChessDataSet, "success": True, "message": "ChessDataSet found in DICOM dataset."}
        else:
            print("Pixel Data (01F7,10cc) not found in DICOM dataset.")
            return {"success": False, "message": "ChessDataSet not found in DICOM dataset."}
    except Exception as e:
        print(f"Error occurred while processing raw file: {e}")
        return {"success": False, "message": f"Error occurred while processing raw file: {e}"}

def getRAWOffset(rawPath: str):
    try:
        res = getChessDataSet(rawPath)
        if not res["success"]:
            print("ChessDataSet not found. Cannot calculate DICOM offset.")
            return {"success": False, "message": "ChessDataSet not found. Cannot calculate DICOM offset."}
        ChessDataSet = res["data"]

        ChessDataStructVersion = struct.unpack("@l", ChessDataSet.value[0:4])[0]
        SeriesInitStructSize = struct.unpack("@l", ChessDataSet.value[4:8])[0]
        NumDicoms = struct.unpack("@l", ChessDataSet.value[8:12])[0]

        ChessDataStructSize = 0
        if ChessDataStructVersion == 100:
            ChessDataStructSize = 111 * 4
        elif ChessDataStructVersion == 200:
            ChessDataStructSize = 416 * 4
        DICOMOffset = ChessDataStructSize + SeriesInitStructSize
        return {"data": DICOMOffset, "success": True, "message": "DICOM offset calculated successfully."}
    except Exception as e:
        print(f"Error occurred while processing raw file: {e}")
        return {"success": False, "message": f"Error occurred while processing raw file: {e}"}

def readRawAndExtractDicom(rawPath: str):
    try:
        res = getChessDataSet(rawPath)
        if not res["success"]:
            return res
        ChessDataSet = res["data"]

        res = getRAWOffset(rawPath)
        if not res["success"]:
            return res  
        DICOMOffset = res["data"]

        ds_new = pydicom.dcmread(BytesIO(ChessDataSet.value[DICOMOffset:]))
        return {"success": True, "message": "DICOM data extracted successfully.", "data": ds_new}
    except Exception as e:
        print(f"Error reading DICOM from raw file: {e}")
        return {"success": False, "message": f"Error reading DICOM from raw file: {e}"}

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