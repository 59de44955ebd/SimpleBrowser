"""
This module provides functions for adding and removing extensions
by changing JSON file 'SecurePreferences' in the profile folder.
Requirement: no WebView2 instance currently using that profile folder.
"""

__all__ = [
    "get_extension_id", "get_extensions", "add_extension", "add_extensions",
    "remove_extension_by_id", "remove_extension_by_path", "remove_missing_extensions",
    "enable_extension_by_id"
]

import hmac
import json
import hashlib
import os
from datetime import datetime

from ctypes import windll, POINTER, byref, create_unicode_buffer
from ctypes.wintypes import *

# Chrome
#SEED = b"\xe7H\xf36\xd8^\xa5\xf9\xdc\xdf%\xd8\xf3G\xa6[L\xdffv\x00\xf0-\xf6rJ*\xf1\x8a!-&\xb7\x88\xa2P\x86\x91\x0c\xf3\xa9\x03\x13ihq\xf3\xdc\x05\x8270\xc9\x1d\xf8\xba\\O\xd9\xc8\x84\xb5\x05\xa8"

# Edge/Chromium/Brave
SEED = b""

EXTENSION_DICT = {
    "account_extension_type": 0,
    "active_permissions": {
        "api": ["cookies", "storage", "tabs", "scripting"],
        "explicit_host": ["<all_urls>"],
        "manifest_permissions": [],
        "scriptable_host": []
    },
    "commands": {},
    "content_settings": [],
    "creation_flags": 38,
    "disable_reasons": [],
    "first_install_time": None,
    "from_webstore": False,
    "granted_permissions": {
        "api": ["cookies", "downloads", "storage", "tabs"],
        "explicit_host": ["<all_urls>"],
        "manifest_permissions": [],
        "scriptable_host": []
    },
    "incognito": True,
    "incognito_content_settings": [],
    "incognito_preferences": {},
    "last_update_time": None,
    "location": 4,
    "newAllowFileAccess": True,
    "path": None,
    "preferences": {},
    "regular_only_preferences": {},
    "service_worker_registration_info": {"version": "1.0"},
    "serviceworkerevents": ["tabs.onUpdated"],
    "was_installed_by_default": False,
    "was_installed_by_oem": False,
    "withholding_permissions": False
}

SECURITY_MAX_SID_SIZE = 68
SID = (BYTE * SECURITY_MAX_SID_SIZE)

advapi32 = windll.advapi32
advapi32.GetUserNameW.argtypes = (LPWSTR, LPDWORD)
advapi32.LookupAccountNameW.argtypes = (LPCWSTR, LPCWSTR, POINTER(SID), LPDWORD, LPWSTR, LPDWORD, LPINT)
advapi32.ConvertSidToStringSidW.argtypes = (POINTER(SID), POINTER(LPWSTR))

########################################
# Auto calculate current user and corresponding SID for you,
# but if targeting another user you will need to change this
########################################
def _get_sid_string() -> str:
    username = create_unicode_buffer(MAX_PATH)
    username_size = DWORD(MAX_PATH)
    advapi32.GetUserNameW(username, byref(username_size))
    sid = SID()
    sid_size = DWORD(SECURITY_MAX_SID_SIZE)
    domainname = create_unicode_buffer(MAX_PATH)
    domainname_size = DWORD(MAX_PATH)
    snu = INT()
    ok = advapi32.LookupAccountNameW(
    	None,                   # use this system
    	username,               # the user to look up
    	sid,                    # the returned SID
    	byref(sid_size),        # the size of the SID returned
    	domainname,             # the returned domain name
    	byref(domainname_size), # the size of the domain name
    	byref(snu)              # the type of sid
    )
    sid_string = LPWSTR()
    ok = advapi32.ConvertSidToStringSidW(sid, byref(sid_string))
    return sid_string.value

########################################
# https://github.com/Pica4x6/SecurePreferencesFile
########################################
def _remove_empty(d):
    if type(d) == dict:
        t = dict(d)
        for x, y in t.items():
            if type(y) == dict:
                if len(y) == 0:
                    del d[x]
                else:
                    _remove_empty(y)
                    if len(y) == 0:
                        del d[x]
            elif type(y) == list:
                if (len(y) == 0):
                    del d[x]
                else:
                    _remove_empty(y)
                    if len(y) == 0:
                        del d[x]
            else:
                if (not y) and (y not in [False, 0]):
                    del d[x]

    elif type(d) == list:
        for x, y in enumerate(d):
            if type(y) == dict:
                if len(y) == 0:
                    del d[x]
                else:
                    _remove_empty(y)
                    if len(y) == 0:
                        del d[x]
            elif type(y) == list:
                if len(y) == 0:
                    del d[x]
                else:
                    _remove_empty(y)
                    if len(y) == 0:
                        del d[x]
            else:
                if (not y) and (y not in [False, 0]):
                    del d[x]

########################################
# https://github.com/Pica4x6/SecurePreferencesFile
########################################
def _calc_hmac(value_as_string: str, path: str, sid: str, seed: bytes) -> str:
    if type(value_as_string) == dict:
        _remove_empty(value_as_string)
    message = sid + path + json.dumps(value_as_string, separators = (",", ":"), ensure_ascii = False).replace("<", "\\u003C").replace("\\u2122", "™")
    hash_obj = hmac.new(seed, message.encode("utf-8"), hashlib.sha256)
    return str(hash_obj.hexdigest().upper())

########################################
# https://github.com/Pica4x6/SecurePreferencesFile
########################################
def _calc_supermac(json_data: dict, sid: str, seed: bytes) -> str:
    data = dict(sorted(json_data.items()))
    # Calculates and sets the super_mac
    super_msg = sid + json.dumps(data["protection"]["macs"]).replace(" ", "")
    hash_obj = hmac.new(seed, super_msg.encode("utf-8"), hashlib.sha256)
    return hash_obj.hexdigest().upper()

########################################
#
########################################
def _calc_chrome_dev_mac(seed: bytes, sid: str, pref_path: str, pref_value) -> str:
    """
    Calculates the HMAC-SHA256 for a Chrome protected preference.

    Parameters:
        seed (bytes): The secret key from PlatformKeys.
        sid (str): The Windows user SID.
        pref_path (str): The full preference path (e.g., "extensions.ui.developer_mode").
        pref_value: The preference value (e.g., True, False, a string, etc.).

    Returns:
        str: The hexadecimal HMAC digest.
    """
    # Serialize the value to canonical JSON (compact, sorted if needed)
    serialized_value = json.dumps(pref_value, separators = (",", ":"), sort_keys = True)

    # Build the input string
    hmac_input = (sid + pref_path + serialized_value).encode("utf-8")

    # Calculate the HMAC-SHA256
    return hmac.new(seed, hmac_input, hashlib.sha256).hexdigest()

########################################
#
########################################
def _encode_install_time(date: datetime) -> int:
    base_date = datetime(1970, 1, 1, 0, 0, 0)
    difference_in_seconds = (date - base_date).total_seconds()
    return int(difference_in_seconds * 1000000) + 11644473600000000

########################################
#
########################################
def get_extension_id(extension_path: str) -> str:
    m = hashlib.sha256()
    m.update(bytes(extension_path.encode("utf-16-le")))
    extension_id = "".join([chr(int(i, base = 16) + ord("a")) for i in m.hexdigest()][:32])
    return extension_id

########################################
#
########################################
def get_extensions(prefs_file: str, external_only: bool = False) -> dict:
    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())
    extensions = {}
    for extension_id, row in data["extensions"]["settings"].items():
        if external_only and row["location"] == 5:
            continue
#        print(extension_id, row["path"])
        extensions[extension_id] = {"path": row["path"], "path_exists": os.path.isdir(row["path"]), "enabled": "disable_reasons" not in row or len(row["disable_reasons"]) == 0}
    return extensions

########################################
#
########################################
def add_extension(prefs_file: str, extension_path: str) -> tuple[str, bool]:
    extension_id = get_extension_id(extension_path)

    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())

    if extension_id in data["extensions"]["settings"]:
        return extension_id, False

    sid = "-".join(_get_sid_string().split("-")[:-1])

    # Dynamically change first_install_time and last_update_time
    encoded_install_time = _encode_install_time(datetime.now())

    extension_dict = dict(EXTENSION_DICT)
    extension_dict["first_install_time"] = str(encoded_install_time)
    extension_dict["last_update_time"] = str(encoded_install_time)
    extension_dict["path"] = extension_path

    data["extensions"]["settings"][extension_id] = extension_dict

    # Calculate hash for [protect][mac]
    data["protection"]["macs"]["extensions"]["settings"][extension_id] = _calc_hmac(extension_dict, f"extensions.settings.{extension_id}", sid, SEED)

    # Set dev mode to true, ensure field exists
    try:
        data["extensions"]["ui"]["developer_mode"] = True
    except KeyError: # means extensions: UI is not found
        data["extensions"].setdefault("ui", {})
        data["extensions"]["ui"]["developer_mode"] = {}
        data["extensions"]["ui"]["developer_mode"] = True

    data["protection"]["macs"]["extensions"]["ui"]["developer_mode"] = _calc_chrome_dev_mac(SEED, sid, "extensions.ui.developer_mode", True)

    # Recalculate and replace super_mac
    data["protection"]["super_mac"] = _calc_supermac(data, sid, SEED)

    with open(prefs_file, "w") as f:
        f.write(json.dumps(data))

    return extension_id, True

########################################
#
########################################
def add_extensions(prefs_file: str, extension_paths: list) -> int:

    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())

    sid = "-".join(_get_sid_string().split("-")[:-1])

    # Dynamically change first_install_time and last_update_time
    encoded_install_time = _encode_install_time(datetime.now())

    extensions_installed = 0

    for extension_path in extension_paths:
        extension_id = get_extension_id(extension_path)
        if extension_id in data["extensions"]["settings"]:
            continue

        extension_dict = dict(EXTENSION_DICT)
        extension_dict["first_install_time"] = str(encoded_install_time)
        extension_dict["last_update_time"] = str(encoded_install_time)
        extension_dict["path"] = extension_path

        data["extensions"]["settings"][extension_id] = extension_dict

        # Calculate hash for [protect][mac]
        path = "extensions.settings.{}".format(extension_id)

        # Add macs to json file
        data["protection"]["macs"]["extensions"]["settings"][extension_id] = _calc_hmac(extension_dict, path, sid, SEED)

        extensions_installed += 1

    if extensions_installed:

        # Set dev mode to true, ensure field exists
        try:
            data["extensions"]["ui"]["developer_mode"] = True

        except KeyError: # means extensions: UI is not found
            # developer_mode = {}
            # ui = {}
            data["extensions"].setdefault("ui", {})

            # now insert your empty dict into developer_mode
            data["extensions"]["ui"]["developer_mode"] = {}
            data["extensions"]["ui"]["developer_mode"] = True
            # print("Need to toggle developer mode")

        # data["extensions"]["ui"]["developer_mode"] = True

        data["protection"]["macs"]["extensions"]["ui"]["developer_mode"] = _calc_chrome_dev_mac(SEED, sid, "extensions.ui.developer_mode", True)

        # Recalculate and replace super_mac
        data["protection"]["super_mac"] = _calc_supermac(data, sid, SEED)

        with open(prefs_file, "w") as f:
            f.write(json.dumps(data))

    return extensions_installed

########################################
#
########################################
def remove_extension_by_id(prefs_file: str, extension_id: str) -> bool:
    sid = "-".join(_get_sid_string().split("-")[:-1])

    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())

    if extension_id not in data["extensions"]["settings"]:
        return False

    del data["extensions"]["settings"][extension_id]
    del data["protection"]["macs"]["extensions"]["settings"][extension_id]

    # Recalculate and replace super_mac
    data["protection"]["super_mac"] = _calc_supermac(data, sid, SEED)

    with open(prefs_file, "w") as f:
        f.write(json.dumps(data))

    return True

########################################
#
########################################
def remove_extension_by_path(prefs_file: str, extension_path: str) -> bool:
    return remove_extension_by_id(prefs_file, get_extension_id(extension_path))

########################################
#
########################################
def remove_missing_extensions(prefs_file: str) -> int:
    sid = "-".join(_get_sid_string().split("-")[:-1])

    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())

    missing_found = 0

    for extension_id, row in dict(data["extensions"]["settings"]).items():
#        if "manifest" in row or row["path"].split("\\")[-2] == "resources":
        if row['location'] == 5:  # resources.pak
            continue

        if not os.path.isdir(row["path"]):
            print("Extension missing:", row["path"])
            missing_found += 1

            del data["extensions"]["settings"][extension_id]
            del data["protection"]["macs"]["extensions"]["settings"][extension_id]

    if missing_found:
        # Recalculate and replace super_mac
        data["protection"]["super_mac"] = _calc_supermac(data, sid, SEED)

        with open(prefs_file, "w") as f:
            f.write(json.dumps(data))

    return missing_found


########################################
#
########################################
def enable_extension_by_id(prefs_file: str, extension_id: str, enabled: bool) -> bool:
    sid = "-".join(_get_sid_string().split("-")[:-1])

    with open(prefs_file, "rb") as f:
        data = json.loads(f.read())

    if extension_id not in data["extensions"]["settings"]:
        return False

    extension_dict = data["extensions"]["settings"][extension_id]

    if "disable_reasons" not in extension_dict:
        pos = list(extension_dict.keys()).index("first_install_time")
        dict_items = list(extension_dict.items())
        dict_items.insert(pos, ("disable_reasons", [] if enabled else [8192]))
#        extension_dict = dict(dict_items)
#        data["extensions"]["settings"][extension_id] = extension_dict
        extension_dict.clear()
        extension_dict.update(dict_items)
    else:
        extension_dict["disable_reasons"] = [] if enabled else [8192]

    # Calculate hash for [protect][mac]
    data["protection"]["macs"]["extensions"]["settings"][extension_id] = _calc_hmac(extension_dict, f"extensions.settings.{extension_id}", sid, SEED)

    # Recalculate and replace super_mac
    data["protection"]["super_mac"] = _calc_supermac(data, sid, SEED)

    with open(prefs_file, "w") as f:
        f.write(json.dumps(data))

    return True


if __name__ == "__main__":
    #PREFS_FILE = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data", "Default", "Secure Preferences")
    PREFS_FILE = r"D:\src\webview2\src\demos\SimpleBrowser\profile\EBWebView\Default\Secure Preferences"

#    extension_id, ok = add_extension(PREFS_FILE, r"D:\src\webview2\src\demos\SimpleBrowser\extensions\jsonview")
#    print("Extension added:", extension_id, ok)

#    res = enable_extension_by_id(PREFS_FILE, "khmdefhplbjflfbekololhneggnidfjk", True)

#    res = enable_extension_by_id(PREFS_FILE, "imkidddokcpgpmclpffjogdnndlbehem", True)
#    print(res)

    for ext_id, ext in get_extensions(PREFS_FILE, True).items():
        print(ext_id, ext)

#    res = remove_extension_by_path(PREFS_FILE, 'D:\\src\\webview2\\src\\demos\\SimpleBrowser\\extensions\\jsonview')
#    res = remove_missing_extensions(PREFS_FILE)
#    print(res)

#    remove_extension(PREFS_FILE, "kggbeahaelfikdkcopagafpfgmghlapi")
#    remove_extension(PREFS_FILE, "jfhfgfaaimaipchmddalcoakofbdbpba")
#    print("Extension removed!")
    pass
