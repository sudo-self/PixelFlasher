#!/usr/bin/env python

import contextlib
import hashlib
import math
import ntpath
import os
import re
import shutil
import sqlite3 as sl
import subprocess
import sys
import time
from datetime import datetime
from urllib.parse import urlparse

import wx
from packaging.version import parse
from platformdirs import *

from config import SDKVERSION, VERSION
from file_editor import FileEditor
from magisk_downloads import MagiskDownloads
from message_box import MessageBox
from message_box_ex import MessageBoxEx
from phone import get_connected_devices
from runtime import *


# ============================================================================
#                               Class FlashFile
# ============================================================================
class FlashFile():
    def __init__(self, linenum = '', platform = '', type = '', command = '', action = '', arg1 = '', arg2 = ''):
        # Instance variables
        self.linenum = linenum
        self.platform = platform
        self.type = type
        self.command = command
        self.action = action
        self.arg1 = arg1
        self.arg2 = arg2

    @property
    def full_line(self):
        response = f"{self.command} {self.action} {self.arg1} {self.arg2}"
        return response.strip()

    @property
    def sync_line(self):
        if self.type in ['init', 'sleep']:
            response = self.type
        elif self.type in ['path', 'if_block']:
            # don't include
            response = ''
        else:
            response = f"{self.command} {self.action} {self.arg1} {self.arg2}"
        return response.strip()


# ============================================================================
#                               Function check_platform_tools
# ============================================================================
def check_platform_tools(self):
    if sys.platform == "win32":
        adb_binary = 'adb.exe'
        fastboot_binary = 'fastboot.exe'
    else:
        adb_binary = 'adb'
        fastboot_binary = 'fastboot'
    if self.config.platform_tools_path:
        adb = os.path.join(self.config.platform_tools_path, adb_binary)
        fastboot = os.path.join(self.config.platform_tools_path, fastboot_binary)
        if os.path.exists(fastboot) and os.path.exists(adb):
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} Selected Platform Tools Path:\n{self.config.platform_tools_path}.")
            adb = os.path.join(self.config.platform_tools_path, adb_binary)
            fastboot = os.path.join(self.config.platform_tools_path, fastboot_binary)
            set_adb(adb)
            set_fastboot(fastboot)
            identify_sdk_version(self)
            print(f"SDK Version: {get_sdk_version()}")
            puml(f":Selected Platform Tools;\nnote left: {self.config.platform_tools_path}\nnote right:{get_sdk_version()}\n")
            return
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: The selected path {self.config.platform_tools_path} does not have adb and or fastboot")
            puml(f"#red:Selected Platform Tools;\nnote left: {self.config.platform_tools_path}\nnote right:The selected path does not have adb and or fastboot\n")
            self.config.platform_tools_path = None
            set_adb(None)
            set_fastboot(None)

    if not self.config.platform_tools_path:
        print("Looking for Android Platform Tools in system PATH environment ...")
        adb = which(adb_binary)
        if adb:
            folder_path = os.path.dirname(adb)
            print(f"Found Android Platform Tools in {folder_path}")
            adb = os.path.join(folder_path, adb_binary)
            fastboot = os.path.join(folder_path, fastboot_binary)
            set_adb(adb)
            set_fastboot(fastboot)
            if os.path.exists(get_fastboot()):
                self.config.platform_tools_path = folder_path
                identify_sdk_version(self)
                print(f"SDK Version: {get_sdk_version()}")
            else:
                print(f"fastboot is not found in: {self.config.platform_tools_path}")
                self.config.platform_tools_path = None
                set_adb(None)
                set_fastboot(None)
        else:
            print("Android Platform Tools is not found.")
    with contextlib.suppress(Exception):
        if self.config.platform_tools_path:
            self.platform_tools_picker.SetPath(self.config.platform_tools_path)
        else:
            self.platform_tools_picker.SetPath('')
    identify_sdk_version(self)


# ============================================================================
#                               Function populate_boot_list
# ============================================================================
def populate_boot_list(self):
    self.list.DeleteAllItems()
    con = get_db()
    con.execute("PRAGMA foreign_keys = ON")
    con.commit()
    sql = """
        SELECT
            BOOT.id as boot_id,
            BOOT.boot_hash,
            BOOT.file_path as boot_path,
            BOOT.is_patched,
            BOOT.magisk_version,
            BOOT.hardware,
            BOOT.epoch as boot_date,
            PACKAGE.id as package_id,
            PACKAGE.boot_hash as package_boot_hash,
            PACKAGE.type as package_type,
            PACKAGE.package_sig,
            PACKAGE.file_path as package_path,
            PACKAGE.epoch as package_date
        FROM BOOT
        JOIN PACKAGE_BOOT
            ON BOOT.id = PACKAGE_BOOT.boot_id
        JOIN PACKAGE
            ON PACKAGE.id = PACKAGE_BOOT.package_id
    """
    if self.config.show_all_boot:
        sql += ";"
    else:
        rom_path = ''
        firmware_path = ''
        if self.config.custom_rom and self.config.advanced_options:
            rom_path = self.config.custom_rom_path
        if self.config.firmware_path:
            firmware_path = self.config.firmware_path
        sql += f"AND package.file_path IN (\'{firmware_path}\', \'{rom_path}\');"

    with con:
        data = con.execute(sql)
        i = 0
        for row in data:
            index = self.list.InsertItem(i, row[1][:8])                     # boot_hash (SHA1)
            self.list.SetItem(index, 1, row[8][:8])                         # package_boot_hash (Source SHA1)
            self.list.SetItem(index, 2, row[10])                            # package_sig (Package Fingerprint)
            self.list.SetItem(index, 3, str(row[4]))                        # magisk_version
            self.list.SetItem(index, 4, row[5])                             # hardware
            ts = datetime.fromtimestamp(row[6])
            self.list.SetItem(index, 5, ts.strftime('%Y-%m-%d %H:%M:%S'))   # boot_date
            self.list.SetItem(index, 6, row[11])                            # package_path
            if row[3]:
                self.list.SetItemColumnImage(i, 0, 0)
            else:
                self.list.SetItemColumnImage(i, 0, -1)
            i += 1
    # auto size columns to largest text, make the last column expand the available room
    cw = 0
    for i in range (0, self.list.ColumnCount - 1):
        self.list.SetColumnWidth(i, -2)
        cw += self.list.GetColumnWidth(i)
    self.list.SetColumnWidth(self.list.ColumnCount - 1, self.list.BestVirtualSize.Width - cw - 5)

    # disable buttons
    self.config.boot_id = None
    self.config.selected_boot_md5 = None
    self.paste_boot.Enable(False)
    if self.list.ItemCount == 0 :
        if self.config.firmware_path:
            print("\nPlease Process the firmware!")
    else:
        print("\nPlease select a boot image!")
    self.patch_boot_button.Enable(False)
    self.process_firmware.SetFocus()
    # we need to do this, otherwise the focus goes on the next control, which is a radio button, and undesired.
    self.delete_boot_button.Enable(False)
    self.boot_folder_button.Enable(False)
    self.firmware_folder_button.Enable(False)
    self.live_boot_button.Enable(False)
    self.flash_boot_button.Enable(False)


# ============================================================================
#                               Function identify_sdk_version
# ============================================================================
def identify_sdk_version(self):
    sdk_version = None
    # Let's grab the adb version
    with contextlib.suppress(Exception):
        if get_adb():
            theCmd = f"\"{get_adb()}\" --version"
            response = run_shell(theCmd)
            if response.stdout:
                for line in response.stdout.split('\n'):
                    if 'Version' in line:
                        sdk_version = line.split()[1]
                        set_sdk_version(sdk_version)
                        # If version is old treat it as bad SDK
                        sdkver = sdk_version.split("-")[0]
                        if parse(sdkver) < parse(SDKVERSION):
                            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Detected older Android Platform Tools version {sdk_version}")
                            # confirm if you want to use older version
                            dlg = wx.MessageDialog(None, f"You have an old Android platform Tools version {sdk_version}\nYou are strongly advised to update to the latest version to avoid any issues\nAre you sure want to continue?",'Old Android Platform Tools',wx.YES_NO | wx.NO_DEFAULT | wx.ICON_EXCLAMATION)
                            result = dlg.ShowModal()
                            puml(f"#red:Selected Platform Tools;\nnote left: {self.config.platform_tools_path}\nnote right:ERROR: Detected older Android Platform Tools version {sdk_version}\n")
                            if result == wx.ID_YES:
                                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User accepted older version {sdk_version} of Android platform tools.")
                                self.scan_button.Enable(True)
                                self.device_choice.Enable(True)
                                puml("#red:User wanted to proceed regardless;\n")
                                return
                            else:
                                print("Older Android platform tools is not accepted. For your protection, disabling device selection.")
                                print("Please update Android SDK.\n")
                                break
                        elif (sdkver in ('34.0.0', '34.0.1')):
                            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Android Platform Tools version {sdkver} has known issues, please select another version.")
                            puml(f"#red:Android Platform Tools version {sdkver} has known issues;\n")
                            dlg = wx.MessageDialog(None, f"Android Platform Tools version {sdkver} has known issues, please select another version.",f"Android Platform Tools {sdkver}",wx.OK | wx.ICON_EXCLAMATION)
                            result = dlg.ShowModal()
                            break
                        else:
                            self.scan_button.Enable(True)
                            self.device_choice.Enable(True)
                            return
    print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Android Platform Tools version is not available or is too old.")
    print("                           For your protection, disabling device selection.")
    print("                           Please select valid Android SDK.\n")
    puml("#pink:For your protection, disabled device selection;\n")
    self.scan_button.Enable(False)
    self.config.device = None
    self.device_choice.SetItems([''])
    self.device_choice.Select(0)
    self.device_choice.Enable(False)


# ============================================================================
#                               Function get_flash_settings
# ============================================================================
def get_flash_settings(self):
    message = ''
    isPatched = ''

    p_custom_rom = self.config.custom_rom and self.config.advanced_options
    p_custom_rom_path = self.config.custom_rom_path
    boot = get_boot()
    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You must first select a valid device.")
        return

    message += f"Android SDK Version:    {get_sdk_version()}\n"
    message += f"Device:                 {self.config.device} {device.hardware} {device.build}\n"
    message += f"Factory Image:          {self.config.firmware_path}\n"
    if p_custom_rom :
        message += f"Custom Rom:             {str(p_custom_rom)}\n"
        message += f"Custom Rom File:        {p_custom_rom_path}\n"
        rom_file = ntpath.basename(p_custom_rom_path)
        set_custom_rom_file(rom_file)
    message += f"\nBoot image:             {boot.boot_hash[:8]} / {boot.package_boot_hash[:8]} \n"
    message += f"                        From: {boot.package_path}\n"
    if boot.is_patched:
        message += f"                        [Patched] with Magisk {boot.magisk_version} on {boot.hardware}\n"
    message += f"\nFlash Mode:             {self.config.flash_mode}\n"
    message += "\n"
    return message


# ============================================================================
#                               Function purge
# ============================================================================
# This function delete multiple files matching a pattern
def purge(dir, pattern):
    for f in os.listdir(dir):
        if re.search(pattern, f):
            os.remove(os.path.join(dir, f))


# ============================================================================
#                               Function delete_all
# ============================================================================
# This function delete multiple files matching a pattern
def delete_all(dir):
    for filename in os.listdir(dir):
        file_path = os.path.join(dir, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")


# ============================================================================
#                               Function debug
# ============================================================================
def debug(message):
    if get_verbose():
        print(f"debug: {message}")


# ============================================================================
#                               Function run_shell
# ============================================================================
# We use this when we want to capture the returncode and also selectively
# output what we want to console. Nothing is sent to console, both stdout and
# stderr are only available when the call is completed.
def run_shell(cmd, timeout=None):
    try:
        response = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='ISO-8859-1', errors="replace", timeout=timeout)
        wx.Yield()
        return response
    except subprocess.TimeoutExpired as e:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Command timed out after {timeout} seconds")
        puml("#red:Command timed out;\n", True)
        puml(f"note right\n{e}\nend note\n")
    except Exception as e:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Encountered an error while executing run_shell")
        print(e)
        puml("#red:Encountered an error;\n", True)
        puml(f"note right\n{e}\nend note\n")
        raise e


# ============================================================================
#                               Function run_shell2
# ============================================================================
# This one pipes the stdout and stderr to Console text widget in realtime,
# no returncode is available.
def run_shell2(cmd, timeout=None):
    try:
        class obj(object):
            pass

        response = obj()
        proc = subprocess.Popen(f"{cmd}", shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='ISO-8859-1', errors="replace")

        print
        stdout = ''
        start_time = time.time()
        while True:
            line = proc.stdout.readline()
            wx.Yield()
            if line.strip() != "":
                print(line.strip())
                stdout += line
            if not line:
                break
            if timeout is not None and time.time() > timeout:
                proc.terminate()
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Command timed out after {timeout} seconds")
                puml("#red:Command timed out;\n", True)
                puml(f"note right\nCommand timed out after {timeout} seconds\nend note\n")
                return None
        proc.wait()
        response.stdout = stdout
        return response
    except Exception as e:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Encountered an error while executing run_shell2")
        print(e)
        puml("#red:Encountered an error;\n", True)
        puml(f"note right\n{e}\nend note\n")
        raise e


# ============================================================================
#                               Function wifi_adb_connect
# ============================================================================
def wifi_adb_connect(self, value, disconnect = False):
    if disconnect:
        command = 'disconnect'
    else:
        command = 'connect'
    print(f"Remote ADB {command}ing: {value}")
    if get_adb():
        puml(":Wifi ADB;\n", True)
        if ':' in value:
            ip,port = value.split(':')
        else:
            ip = value.strip()
            port = '5555'
        theCmd = f"\"{get_adb()}\" {command} {ip}:{port}"
        res = run_shell(theCmd)
        puml(f"note right\n=== {command} to: {ip}:{port}\nend note\n")
        if res.returncode == 0 and 'cannot' not in res.stdout and 'failed' not in res.stdout:
            print(f"ADB {command}ed: {ip}:{port}")
            puml(f"#palegreen:Succeeded;\n")
            self.device_choice.SetItems(get_connected_devices())
            self._select_configured_device()
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Could not {command} {ip}:{port}\n")
            print(f"{res.stderr}")
            print(f"{res.stdout}")
            puml(f"#red:**Failed**\n{res.stderr}\n{res.stdout};\n")


# ============================================================================
#                               Function adb_kill_server
# ============================================================================
def adb_kill_server(self):
    if get_adb():
        print("Invoking adb kill-server ...")
        puml(":adb kill-server;\n", True)
        theCmd = f"\"{get_adb()}\" kill-server"
        res = run_shell(theCmd)
        if res.returncode == 0:
            print("returncode: 0")
            puml(f"#palegreen:Succeeded;\n")
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Could not kill adb server.\n")
            print(f"{res.stderr}")
            print(f"{res.stdout}")
            puml(f"#red:**Failed**\n{res.stderr}\n{res.stdout};\n")
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Missing Android platform tools.\n")
        puml(f"#red:Missing Android platform tools;\n")


# ============================================================================
#                               Function md5
# ============================================================================
def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


# ============================================================================
#                               Function sha1
# ============================================================================
def sha1(fname):
    hash_sha1 = hashlib.sha1()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha1.update(chunk)
    return hash_sha1.hexdigest()


# ============================================================================
#                               Function sha256
# ============================================================================
def sha256(fname):
    hash_sha256 = hashlib.sha256()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)
    return hash_sha256.hexdigest()


# ============================================================================
#                               Function get_code_page
# ============================================================================
def get_code_page():
    if sys.platform != "win32":
        return
    cp = get_system_codepage()
    if cp:
        print(f"Active code page: {cp}")
    else:
        theCmd = "chcp"
        res = run_shell(theCmd)
        if res.returncode == 0:
            # extract the code page portion
            try:
                debug(f"CP: {res.stdout}")
                cp = res.stdout.split(":")
                cp = cp[1].strip()
                cp = int(cp.replace('.',''))
                print(f"Active code page: {cp}")
                set_system_codepage(cp)
            except Exception:
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to get Active code page.\n")
                print(f"{res.stderr}")
                print(f"{res.stdout}")
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to get Active code page.\n")


# ============================================================================
#                               Function Which
# ============================================================================
def which(program):
    import os
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


# ============================================================================
#                               Function create_support_zip
# ============================================================================
def create_support_zip():
    print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} Creating support.zip file ...")
    config_path = get_config_path()
    tmp_dir_full = os.path.join(config_path, 'tmp')
    support_dir_full = os.path.join(config_path, 'support')
    support_zip = os.path.join(tmp_dir_full, 'support.zip')

    # if a previous support dir exist delete it allong with support.zip
    if os.path.exists(support_dir_full):
        debug("Deleting old support files ...")
        delete_all(support_dir_full)
    if os.path.exists(support_zip):
        debug("Deleting old support.zip ...")
        os.remove(support_zip)

    # create support folder if it does not exist
    if not os.path.exists(support_dir_full):
        os.makedirs(support_dir_full, exist_ok=True)

    # copy PixelFlasher.json to tmp\support folder
    to_copy = os.path.join(config_path, 'PixelFlasher.json')
    if os.path.exists(to_copy):
        debug(f"Copying {to_copy} to {support_dir_full}")
        shutil.copy(to_copy, support_dir_full, follow_symlinks=True)
    # copy PixelFlasher.db to tmp\support folder
    to_copy = os.path.join(config_path, get_pf_db())
    if os.path.exists(to_copy):
        debug(f"Copying {to_copy} to {support_dir_full}")
        shutil.copy(to_copy, support_dir_full, follow_symlinks=True)
    # copy labels.json to tmp\support folder
    to_copy = os.path.join(config_path, 'labels.json')
    if os.path.exists(to_copy):
        debug(f"Copying {to_copy} to {support_dir_full}")
        shutil.copy(to_copy, support_dir_full, follow_symlinks=True)
    # copy logs to support folder
    to_copy = os.path.join(config_path, 'logs')
    logs_dir = os.path.join(support_dir_full, 'logs')
    if os.path.exists(to_copy):
        debug(f"Copying {to_copy} to {support_dir_full}")
        shutil.copytree(to_copy, logs_dir)
    # copy puml to support folder
    to_copy = os.path.join(config_path, 'puml')
    puml_dir = os.path.join(support_dir_full, 'puml')
    if os.path.exists(to_copy):
        debug(f"Copying {to_copy} to {support_dir_full}")
        shutil.copytree(to_copy, puml_dir)

    # create directory/file listing
    if sys.platform == "win32":
        theCmd = f"dir /s /b \"{config_path}\" > \"{os.path.join(support_dir_full, 'files.txt')}\""
    else:
        theCmd = f"ls -lRgn \"{config_path}\" > \"{os.path.join(support_dir_full, 'files.txt')}\""
    debug(f"{theCmd}")
    res = run_shell(theCmd)

    # sanitize json
    file_path = os.path.join(support_dir_full, 'PixelFlasher.json')
    if os.path.exists(file_path):
        sanitize_file(file_path)
    # sanitize files.txt
    file_path = os.path.join(support_dir_full, 'files.txt')
    if os.path.exists(file_path):
        sanitize_file(file_path)

    # for each file in logs, sanitize
    for filename in os.listdir(logs_dir):
        file_path = os.path.join(logs_dir, filename)
        if os.path.exists(file_path):
            sanitize_file(file_path)

    # for each file in logs, sanitize
    for filename in os.listdir(puml_dir):
        file_path = os.path.join(puml_dir, filename)
        if os.path.exists(file_path):
            sanitize_file(file_path)

    # sanitize db
    file_path = os.path.join(support_dir_full, get_pf_db())
    if os.path.exists(file_path):
        sanitize_db(file_path)

    # zip support folder
    debug(f"Zipping {support_dir_full} ...")
    shutil.make_archive(support_dir_full, 'zip', support_dir_full)


# ============================================================================
#                               Function sanitize_file
# ============================================================================
def sanitize_file(filename):
    debug(f"Santizing {filename} ...")
    with contextlib.suppress(Exception):
        with open(filename, "rt", encoding='ISO-8859-1', errors="replace") as fin:
            data = fin.read()
        data = re.sub(r'(\\Users\\+)(?:.*?)(\\+)', r'\1REDACTED\2', data, flags=re.IGNORECASE)
        data = re.sub(r'(\/Users\/+)(?:.*?)(\/+)', r'\1REDACTED\2', data, flags=re.IGNORECASE)
        data = re.sub(r'(\"device\":\s+)(\"\w+?\")', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(device\sid:\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(device:\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(Rebooting device\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(Flashing device\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(waiting for\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(Serial\sNumber\.+\:\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(fastboot(.exe)?\"? -s\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(adb(.exe)?\"? -s\s+)(\w+)', r'\1REDACTED', data, flags=re.IGNORECASE)
        data = re.sub(r'(\S\  \((?:adb|f\.b|rec|sid)\)   )(.+?)(\s+.*)', r'\1REDACTED\3', data, flags=re.IGNORECASE)
        with open(filename, "wt", encoding='ISO-8859-1', errors="replace") as fin:
            fin.write(data)


# ============================================================================
#                               Function sanitize_db
# ============================================================================
def sanitize_db(filename):
    debug(f"Santizing {filename} ...")
    con = sl.connect(filename)
    cursor = con.cursor()
    with con:
        data = con.execute("SELECT id, file_path FROM BOOT")
        for row in data:
            id = row[0]
            file_path = row[1]
            if sys.platform == "win32":
                file_path_sanitized = re.sub(r'(\\Users\\+)(?:.*?)(\\+)', r'\1REDACTED\2', file_path, flags=re.IGNORECASE)
            else:
                file_path_sanitized = re.sub(r'(\/Users\/+)(?:.*?)(\/+)', r'\1REDACTED\2', file_path, flags=re.IGNORECASE)
            cursor.execute(f"Update BOOT set file_path = '{file_path_sanitized}' where id = {id}")
            con.commit()
    with con:
        data = con.execute("SELECT id, file_path FROM PACKAGE")
        for row in data:
            id = row[0]
            file_path = row[1]
            if sys.platform == "win32":
                file_path_sanitized = re.sub(r'(\\Users\\+)(?:.*?)(\\+)', r'\1REDACTED\2', file_path, flags=re.IGNORECASE)
            else:
                file_path_sanitized = re.sub(r'(\/Users\/+)(?:.*?)(\/+)', r'\1REDACTED\2', file_path, flags=re.IGNORECASE)
            cursor.execute(f"Update PACKAGE set file_path = '{file_path_sanitized}' where id = {id}")
            con.commit()


# ============================================================================
#                               Function set_flash_button_state
# ============================================================================
def set_flash_button_state(self):
    try:
        boot = get_boot()
        if self.config.firmware_path != '' and os.path.exists(boot.package_path):
            self.flash_button.Enable()
        else:
            self.flash_button.Disable()
    except Exception:
        self.flash_button.Disable()


# ============================================================================
#                               Function select_firmware
# ============================================================================
def select_firmware(self):
    puml(":Selecting Firmware;\n", True)
    firmware = ntpath.basename(self.config.firmware_path)
    filename, extension = os.path.splitext(firmware)
    extension = extension.lower()
    if extension == '.zip':
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} The following firmware is selected:\n{firmware}")
        firmware_hash = sha256(self.config.firmware_path)
        print(f"Selected Firmware {firmware} SHA-256: {firmware_hash}")
        puml(f"note right\n{firmware}\nSHA-256: {firmware_hash}\nend note\n")

        # Check to see if the first 8 characters of the checksum is in the filename, Google published firmwares do have this.
        if firmware_hash[:8] in firmware:
            print(f"Expected to match {firmware_hash[:8]} in the filename and did. This is good!")
            puml(f"#CDFFC8:Checksum matches portion of the filename {firmware};\n")
        else:
            print(f"WARNING: Expected to match {firmware_hash[:8]} in the filename but didn't, please double check to make sure the checksum is good.")
            puml("#orange:Unable to match the checksum in the filename;\n")

        set_lineage(False)
        if 'lineage' in filename:
            print("Warning: Detected Lineage (Non-Pixel) firmware.\nBoot extraction and patching is supported, however avoid full factory flashing and instead use Lineage Recovery for updates.")
            puml("#orange:Detected Lineage (Non-Pixel) firmware.;\n")
            puml("note right\nBoot extraction and patching is supported\nhowever avoid full factory flashing\nand instead use Lineage Recovery for updates.\nend note\n")
            set_lineage(True)
            set_firmware_model(filename)
            set_firmware_id(filename)
        else:
            firmware = filename.split("-")
            if len(firmware) == 1:
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: The selected firmware filename is not a valid name.\nPlease keep the original filename intact.\n")
                self.config.firmware_path = None
                self.firmware_picker.SetPath('')
                set_firmware_id(None)
                puml("#red:The selected firmware filename is not valid;\n")
                return f"SHA-256: {firmware_hash}"
            else:
                try:
                    set_firmware_model(firmware[0])
                    set_firmware_id(f"{firmware[0]}-{firmware[1]}")
                except Exception as e:
                    set_firmware_model(None)
                    set_firmware_id(filename)
        if get_firmware_id():
            set_flash_button_state(self)
        else:
            self.flash_button.Disable()
        populate_boot_list(self)
        return f"SHA-256: {firmware_hash}"
    else:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: The selected file {firmware} is not a zip file.")
        puml("#red:The selected firmware is not valid;\n")
        self.config.firmware_path = None
        self.firmware_picker.SetPath('')
        return 'Select Pixel Firmware'


# ============================================================================
#                               Function process_file
# ============================================================================
def process_file(self, file_type):
    print("")
    print("==============================================================================")
    print(f" {datetime.now():%Y-%m-%d %H:%M:%S} PixelFlasher {VERSION}         Processing {file_type} file ...")
    print("==============================================================================")
    puml(f"#cyan:Process {file_type};\n", True)
    config_path = get_config_path()
    path_to_7z = get_path_to_7z()
    boot_images = os.path.join(config_path, get_boot_images_dir())
    tmp_dir_full = os.path.join(config_path, 'tmp')
    con = get_db()
    con.execute("PRAGMA foreign_keys = ON")
    con.commit()
    cursor = con.cursor()
    start_1 = time.time()
    checksum = ''

    if file_type == 'firmware':
        file_to_process = self.config.firmware_path
        factory_images = os.path.join(config_path, 'factory_images')
        package_sig = get_firmware_id()
        package_dir_full = os.path.join(factory_images, package_sig)
        # skip zip extraction if we're dealing with lineage firmware
        if get_lineage():
            image_file_path = file_to_process
        else:
            image_file_path = os.path.join(package_dir_full, f"image-{package_sig}.zip")
            # Unzip the factory image
            debug(f"Unzipping Image: {file_to_process} into {package_dir_full} ...")
            theCmd = f"\"{path_to_7z}\" x -bd -y -o\"{factory_images}\" \"{file_to_process}\""
            debug(theCmd)
            res = run_shell2(theCmd)
    else:
        file_to_process = self.config.custom_rom_path
        package_sig = get_custom_rom_id()
        image_file_path = file_to_process
    puml(f"note right:{image_file_path}\n")

    # see if we have a record for the firmware/rom being processed
    cursor.execute(f"SELECT ID, boot_hash FROM PACKAGE WHERE package_sig = '{package_sig}' AND file_path = '{file_to_process}'")
    data = cursor.fetchall()
    if len(data) > 0:
        pre_package_id = data[0][0]
        pre_checksum = data[0][1]
        debug(f"Found a previous {file_type} PACKAGE record id={pre_package_id} for package_sig: {package_sig} Firmware: {file_to_process}")
    else:
        pre_package_id = 0
        pre_checksum = 'x'

    # delete all files in tmp folder to make sure we're dealing with new files only.
    delete_all(tmp_dir_full)

    if not os.path.exists(image_file_path):
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: The firmware file did not have the expected structure / contents.")
        if file_type == 'firmware':
            print(f"Please check {self.config.firmware_path} to make sure it is a valid factory image file.")
            puml("#red:The selected firmware is not valid;\n")
        print("Aborting ...\n")
        return

    # extract boot.img or init_boot.img
    if 'panther' in get_firmware_model() or 'cheetah' in get_firmware_model():
        boot_file_name = 'init_boot.img'
        files_to_extract = 'boot.img init_boot.img'
    else:
        boot_file_name = 'boot.img'
        files_to_extract = 'boot.img'
    print(f"Extracting {boot_file_name} from {image_file_path} ...")
    puml(f":Extract {boot_file_name};\n")
    theCmd = f"\"{path_to_7z}\" x -bd -y -o\"{tmp_dir_full}\" \"{image_file_path}\" {files_to_extract}"
    debug(f"{theCmd}")
    res = run_shell(theCmd)
    # expect ret 0
    if res.returncode != 0:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Could not extract {boot_file_name}.")
        print(res.stderr)
        puml(f"#red:ERROR: Could not extract {boot_file_name};\n")
        print("Aborting ...\n")
        return
    # sometimes the return code is 0 but no file to extract, handle that case.
    boot_img_file = os.path.join(tmp_dir_full, boot_file_name)
    if not os.path.exists(boot_img_file):
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Could not extract {boot_file_name}, ")
        print(f"Please make sure the file: {image_file_path} has {boot_file_name} in it.")
        puml(f"#red:ERROR: Could not extract {boot_file_name};\n")
        print("Aborting ...\n")
        return

    # get the checksum of the boot_file_name
    checksum = sha1(os.path.join(boot_img_file))
    print(f"sha1 of {boot_file_name}: {checksum}")
    puml(f"note right:sha1 of {boot_file_name}: {checksum}\n")

    # if a matching boot_file_name is not found, store it.
    cached_boot_img_dir_full = os.path.join(boot_images, checksum)
    cached_boot_img_path = os.path.join(cached_boot_img_dir_full, boot_file_name)
    print(f"Checking for cached copy of {boot_file_name}")
    if not os.path.exists(cached_boot_img_dir_full):
        os.makedirs(cached_boot_img_dir_full, exist_ok=True)
    if not os.path.exists(cached_boot_img_path):
        print(f"Cached copy of {boot_file_name} with sha1: {checksum} is not found.")
        print(f"Copying {image_file_path} to {cached_boot_img_dir_full}")
        shutil.copy(boot_img_file, cached_boot_img_dir_full, follow_symlinks=True)
        if 'panther' in get_firmware_model() or 'cheetah' in get_firmware_model():
            # we need to copy boot.img for Pixel 7, 7P so that we can do live boot.
            shutil.copy(os.path.join(tmp_dir_full, 'boot.img'), cached_boot_img_dir_full, follow_symlinks=True)
    else:
        print(f"Found a cached copy of {file_type} {boot_file_name} sha1={checksum}")

    # create PACKAGE db record
    sql = 'INSERT INTO PACKAGE (boot_hash, type, package_sig, file_path, epoch ) values(?, ?, ?, ?, ?) ON CONFLICT (file_path) DO NOTHING'
    data = checksum, file_type, package_sig, file_to_process, time.time()
    try:
        cursor.execute(sql, data)
        con.commit()
    except Exception as e:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Encountered an error.")
        print(e)
    package_id = cursor.lastrowid
    print(f"Package ID: {package_id}")
    # if we didn't insert a new record, let's use the pre_package_id in case we need to insert a record into PACKAGE_BOOT
    if package_id == 0:
        package_id = pre_package_id

    # create BOOT db record
    sql = 'INSERT INTO BOOT (boot_hash, file_path, is_patched, magisk_version, hardware, epoch) values(?, ?, ?, ?, ?, ?) ON CONFLICT (boot_hash) DO NOTHING'
    data = checksum, cached_boot_img_path, 0, '', '', time.time()
    try:
        cursor.execute(sql, data)
        con.commit()
    except Exception as e:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Encountered an error.")
        print(e)
    boot_id = cursor.lastrowid
    print(f"Boot ID: {boot_id}")
    # if boot_id record does not exist, set it to 0
    cursor.execute(f"SELECT ID FROM BOOT WHERE id = '{boot_id}'")
    data = cursor.fetchall()
    if len(data) == 0:
        boot_id = 0
    # if we didn't insert in BOOT or id does not exist, see if we have a record for the boot being processed in case we need to insert a record into PACKAGE_BOOT
    if boot_id == 0:
        cursor.execute(f"SELECT ID FROM BOOT WHERE boot_hash = '{pre_checksum}' OR boot_hash = '{checksum}'")
        data = cursor.fetchall()
        if len(data) > 0:
            boot_id = data[0][0]
            print(f"Found a previous BOOT record id={boot_id} for boot_hash: {pre_checksum} or {checksum}")
        else:
            boot_id = 0

    # create PACKAGE_BOOT db record
    if package_id > 0 and boot_id > 0:
        debug(f"Creating PACKAGE_BOOT record, package_id: {package_id} boot_id: {boot_id}")
        sql = 'INSERT INTO PACKAGE_BOOT (package_id, boot_id, epoch) values(?, ?, ?) ON CONFLICT (package_id, boot_id) DO NOTHING'
        data = package_id, boot_id, time.time()
        try:
            cursor.execute(sql, data)
            con.commit()
            package_boot_id = cursor.lastrowid
            if package_boot_id == 0:
                print(f"Record PACKAGE_BOOT record, package_id: {package_id} boot_id: {boot_id} already exists")
            else:
                print(f"Package_Boot ID: {package_boot_id}")
        except Exception as e:
            print(f"Record PACKAGE_BOOT record, package_id: {package_id} boot_id: {boot_id} already exists")

    set_db(con)
    populate_boot_list(self)
    end_1 = time.time()
    print(f"Process {file_type} time: {math.ceil(end_1 - start_1)} seconds")
    print("------------------------------------------------------------------------------\n")


# ============================================================================
#                               Function process_flash_all_file
# ============================================================================
def process_flash_all_file(filepath):
    cwd = os.getcwd()
    flash_file_lines = []
    with open(filepath) as fp:
        #1st line, platform
        line = fp.readline()
        if line[:9] == "@ECHO OFF":
            filetype = 'bat'
        elif line[:9] == "#!/bin/sh":
            filetype = 'sh'
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unexpected first line: {line} in file: {filepath}")
        flash = FlashFile(1, platform = filetype, type = "init", command = line.strip())
        flash_file_lines.append(flash)

        cnt = 1
        in_if_block = False
        if_block_data = ''
        while line:
            line = fp.readline()

            #---------------------------------
            # Line that should not be captured
            if line.strip() == '':
                # blank line, ignore it
                continue
            elif line[:2] == "::":
                # comment line windows, ignore it
                continue
            elif line[:1] == "#":
                # comment line Linux, ignore it
                continue
            elif line[:10] == "pause >nul":
                # pause line, ignore it
                continue
            elif line[:4] == "exit":
                # exit line, ignore it
                continue
            elif line[:26] == "echo Press any key to exit":
                # exit line, ignore it
                continue

            #-----------------------
            # line that are relevant
            elif line[:4] == "if !":
                # if line to check fastboot version, grab it differently (all as one block)
                in_if_block = True
                if_block_data += line
                continue
            elif line[:7] == "  echo ":
                # part of the previous if, grab it differently (all as one block)
                if in_if_block:
                    if_block_data += line
                continue
            elif line[:6] == "  exit":
                # part of the previous if, grab it differently (all as one block)
                if in_if_block:
                    if_block_data += line
                continue
            elif line[:2] == "fi":
                # part of the previous if, grab it differently (all as one block)
                if in_if_block:
                    if_block_data += line
                in_if_block = False
                flash = FlashFile(cnt, platform = filetype, type = "if_block", command = if_block_data.strip())
                flash_file_lines.append(flash)
                continue
            elif line[:5] == "PATH=":
                flash = FlashFile(cnt, platform = filetype, type = "path", command = line.strip())
                flash_file_lines.append(flash)
                continue

            elif line[:5] == "ping " or line[:6] == "sleep ":
                flash = FlashFile(cnt, platform = filetype, type = "sleep", command = line.strip())
                flash_file_lines.append(flash)
                continue

            elif line[:8] == "fastboot":
                parts = line.split()
                if parts[1] == 'flash':
                    flash = FlashFile(cnt, platform = filetype, type = "fastboot", command = "fastboot", action = "flash", arg1 = parts[2], arg2 = parts[3])
                    flash_file_lines.append(flash)
                    continue
                elif parts[1] == 'reboot-bootloader':
                    flash = FlashFile(cnt, platform = filetype, type = "fastboot", command = "fastboot", action = "reboot-bootloader")
                    flash_file_lines.append(flash)
                    continue
                elif parts[1] == '-w' and parts[2] == 'update':
                    flash = FlashFile(cnt, platform = filetype, type = "fastboot", command = "fastboot", action = "-w update", arg1 = parts[3])
                    flash_file_lines.append(flash)
                    continue
                else:
                    print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR! Encountered an unexpected fastboot line while parsing {filepath}")
                    print(line)
                    return "ERROR"

            #-----------------
            # Unexpected lines
            else:
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR! Encountered an unexpected line while parsing {filepath}")
                print(line)
                return "ERROR"

            cnt += 1
        return flash_file_lines


# ============================================================================
#                               Function get_ui_cooridnates
# ============================================================================
def get_ui_cooridnates(xmlfile, search):
    with open(xmlfile, "r", encoding='ISO-8859-1', errors="replace") as fin:
        data = fin.read()
    regex = re.compile(f"{search}.*?bounds\=\"\[(\d+),(\d+)\]\[(\d+),(\d+)\]\".+")
    m = re.findall(regex, data)
    if m:
        debug(f"Found Bounds: {m[0][0]} {m[0][1]} {m[0][2]} {m[0][3]}")
        x = (int(m[0][0]) + int(m[0][2])) / 2
        y = (int(m[0][1]) + int(m[0][3])) / 2
        debug(f"Click Coordinates: {int(x)} {int(y)}")
        return f"{x} {y}"


# ============================================================================
#                               Function extract_sha1
# ============================================================================
def extract_sha1(binfile, length = 8):
    with open(binfile, 'rb') as f:
        s = f.read()
        # Find SHA1=
        pos = s.find(b'\x53\x48\x41\x31\x3D')
        # Move to that location
        if pos != -1:
            # move to 5 characters from the found position
            f.seek(pos + 5, 0)
            # read length bytes
            res = f.read(length)
            return res.decode("utf-8")


# ============================================================================
#                               Function extract_fingerprint
# ============================================================================
def extract_fingerprint(binfile):
    with open(binfile, 'rb') as f:
        s = f.read()
        # Find fingerprint=
        pos = s.find(b'\x66\x69\x6E\x67\x65\x72\x70\x72\x69\x6E\x74')
        # Move to that location
        if pos != -1:
            # move to 12 characters from the found position
            f.seek(pos + 12, 0)
            # read 65 bytes
            res = f.read(65)
            return res.decode("utf-8")


# # ============================================================================
# #                               Function drive_magisk (not used)
# # ============================================================================
# def drive_magisk(self, boot_file_name):
#     start = time.time()
#     print("")
#     print("==============================================================================")
#     print(f" {datetime.now():%Y-%m-%d %H:%M:%S} PixelFlasher {VERSION}              Driving Magisk ")
#     print("==============================================================================")

#     device = get_phone()
#     config_path = get_config_path()

#     if not device.is_display_unlocked():
#         title = "Display is Locked!"
#         message =  "ERROR: Your phone display is Locked.\n\n"
#         message += "Make sure you unlock your display\n"
#         message += "And set the display timeout to at least 1 minute.\n\n"
#         message += "After doing so, Click OK to accept and continue.\n"
#         message += "or Hit CANCEL to abort."
#         print(f"\n*** Dialog ***\n{message}\n______________\n")
#         dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
#         result = dlg.ShowModal()
#         if result == wx.ID_OK:
#             print("User pressed ok.")
#             if not device.is_display_unlocked():
#                 print("ERROR: The device display is still Locked!\nAborting ...\n")
#                 return 'ERROR'
#         else:
#             print("User pressed cancel.")
#             print("Aborting ...\n")
#             return 'ERROR'

#     # Get uiautomator dump of view1
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell uiautomator dump {self.config.phone_path}/view1.xml"
#     debug(theCmd)
#     res = run_shell(theCmd)
#     if res.returncode != 0:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: uiautomator dump failed.")
#         print(res.stderr)
#         return 'ERROR'

#     # Pull view1.xml
#     view1 = os.path.join(config_path, 'tmp', 'view1.xml')
#     print(f"Pulling {self.config.phone_path}/view1.xml from the phone ...")
#     theCmd = f"\"{get_adb()}\" -s {device.id} pull {self.config.phone_path}/view1.xml \"{view1}\""
#     debug(theCmd)
#     res = run_shell(theCmd)
#     # expect ret 0
#     if res.returncode == 1:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to pull {view1} from phone.")
#         print(res.stderr)
#         print("Aborting ...\n")
#         return 'ERROR'

#     # get view1 bounds / click coordinates
#     coords = get_ui_cooridnates(view1, "Install")

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Click on coordinates of `Install`
#     # For Pixel 6 this would be: adb shell input tap 830 417
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input tap {coords}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 2 seconds
#     print("Sleeping 2 seconds to make sure the view is loaded ...")
#     time.sleep(2)

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Get uiautomator dump of view2
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell uiautomator dump {self.config.phone_path}/view2.xml"
#     debug(theCmd)
#     res = run_shell(theCmd)
#     if res.returncode != 0:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: uiautomator dump failed.")
#         print(res.stderr)
#         # print("Please launch Magisk manually.")
#         return 'ERROR'

#     # Pull view2.xml
#     view2 = os.path.join(config_path, 'tmp', 'view2.xml')
#     print(f"Pulling {self.config.phone_path}/view2.xml from the phone ...")
#     theCmd = f"\"{get_adb()}\" -s {device.id} pull {self.config.phone_path}/view2.xml \"{view2}\""
#     debug(theCmd)
#     res = run_shell(theCmd)
#     # expect ret 0
#     if res.returncode == 1:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to pull {view2} from phone.")
#         print(res.stderr)
#         print("Aborting ...\n")
#         return 'ERROR'

#     # get view2 bounds / click coordinates
#     coords = get_ui_cooridnates(view2, "Select and Patch a File")

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Click on coordinates of `Select and Patch a File`
#     # For Pixel 6 this would be: adb shell input tap 540 555
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input tap {coords}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 2 seconds
#     print("Sleeping 2 seconds to make sure the view is loaded ...")
#     time.sleep(2)

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Get uiautomator dump of view3
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell uiautomator dump {self.config.phone_path}/view3.xml"
#     debug(theCmd)
#     res = run_shell(theCmd)
#     if res.returncode != 0:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: uiautomator dump failed.")
#         print(res.stderr)
#         return 'ERROR'

#     # Pull view3.xml
#     view3 = os.path.join(config_path, 'tmp', 'view3.xml')
#     print(f"Pulling {self.config.phone_path}/view3.xml from the phone ...")
#     theCmd = f"\"{get_adb()}\" -s {device.id} pull {self.config.phone_path}/view3.xml \"{view3}\""
#     debug(theCmd)
#     res = run_shell(theCmd)
#     # expect ret 0
#     if res.returncode == 1:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to pull {view3} from phone.")
#         print(res.stderr)
#         print("Aborting ...\n")
#         return 'ERROR'

#     # get view3 bounds / click coordinates
#     coords = get_ui_cooridnates(view3, "Search this phone")

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Click on coordinates of `Search this phone`
#     # For Pixel 6 this would be: adb shell input tap 574 210
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input tap {coords}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 2 seconds
#     print("Sleeping 2 seconds to make sure the view is loaded ...")
#     time.sleep(2)

#     # Type the boot_file_name to search for it
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input text {boot_file_name}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 1 seconds
#     print("Sleeping 1 seconds to make sure the view is loaded ...")
#     time.sleep(1)

#     # Hit Enter to search
#     print("Hitting Enter to search")
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input keyevent 66"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 1 seconds
#     print("Sleeping 1 seconds to make sure the view is loaded ...")
#     time.sleep(1)

#     # Hit Enter to Select it
#     print("Hitting Enter to select")
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input keyevent 66"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 2 seconds
#     print("Sleeping 2 seconds to make sure the view is loaded ...")
#     time.sleep(2)

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Get uiautomator dump of view4
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell uiautomator dump {self.config.phone_path}/view4.xml"
#     debug(theCmd)
#     res = run_shell(theCmd)
#     if res.returncode != 0:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: uiautomator dump failed.")
#         print(res.stderr)
#         return 'ERROR'

#     # Pull view4.xml
#     view4 = os.path.join(config_path, 'tmp', 'view4.xml')
#     print(f"Pulling {self.config.phone_path}/view4.xml from the phone ...")
#     theCmd = f"\"{get_adb()}\" -s {device.id} pull {self.config.phone_path}/view4.xml \"{view4}\""
#     debug(theCmd)
#     res = run_shell(theCmd)
#     # expect ret 0
#     if res.returncode == 1:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to pull {view4} from phone.")
#         print(res.stderr)
#         print("Aborting ...\n")
#         return 'ERROR'

#     # get view4 bounds / click coordinates
#     coords = get_ui_cooridnates(view4, "LET'S GO")

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Click on coordinates of `LET'S GO`
#     # For Pixel 6 this would be: adb shell input tap 839 417
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input tap {coords}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # Sleep 2 seconds
#     print("Sleeping 2 seconds to make sure the view is loaded ...")
#     time.sleep(2)

#     # Sleep 10 seconds
#     print("Sleeping 10 seconds to make sure Patching is completed ...")
#     time.sleep(10)

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Get uiautomator dump of view5
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell uiautomator dump {self.config.phone_path}/view5.xml"
#     debug(theCmd)
#     res = run_shell(theCmd)
#     if res.returncode != 0:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: uiautomator dump failed.")
#         print(res.stderr)
#         return 'ERROR'

#     # Pull view5.xml
#     view5 = os.path.join(config_path, 'tmp', 'view5.xml')
#     print(f"Pulling {self.config.phone_path}/view5.xml from the phone ...")
#     theCmd = f"\"{get_adb()}\" -s {device.id} pull {self.config.phone_path}/view5.xml \"{view5}\""
#     debug(theCmd)
#     res = run_shell(theCmd)
#     # expect ret 0
#     if res.returncode == 1:
#         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to pull {view5} from phone.")
#         print(res.stderr)
#         print("Aborting ...\n")
#         return 'ERROR'

#     # get view5 bounds / click coordinates (Save button)
#     coords = get_ui_cooridnates(view5, "com.topjohnwu.magisk:id/action_save")

#     # Check for Display being locked again
#     if not device.is_display_unlocked():
#         print("ERROR: The device display is Locked!\nAborting ...\n")
#         return 'ERROR'

#     # Click on coordinates of `com.topjohnwu.magisk:id/action_save`
#     # For Pixel 6 this would be: adb shell input tap 1010 198
#     theCmd = f"\"{get_adb()}\" -s {device.id} shell input tap {coords}"
#     debug(theCmd)
#     res = run_shell(theCmd)

#     # get view5 bounds / click coordinates (All Done)
#     coords = None
#     coords = get_ui_cooridnates(view5, "- All done!")
#     if coords:
#         print("\nIt looks liks Patching was successful.")
#     else:
#         print("\nIt looks liks Patching was not successful.")

#     end = time.time()
#     print(f"Magisk Version: {device.magisk_version}")
#     print(f"Driven Patch time: {math.ceil(end - start)} seconds")
#     print("------------------------------------------------------------------------------\n")


# ============================================================================
#                               Function patch_boot_img
# ============================================================================
def patch_boot_img(self, custom_patch = False):
    custom_text = ""
    if custom_patch:
        custom_text = "Custom "
    print("")
    print("==============================================================================")
    print(f" {datetime.now():%Y-%m-%d %H:%M:%S} PixelFlasher {VERSION}              Patching {custom_text}boot")
    print("==============================================================================")
    puml(f"#cyan:Create {custom_text}Patch;\n", True)
    puml("partition \"**Create Patch**\" {\n")

    # get device
    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You must first select a valid device.")
        print("Aborting ...\n")
        puml("#red:Valid device is not selected;\n}\n")
        return

    if custom_patch:
        with wx.FileDialog(self, "boot / init_boot image to create patch from.", '', '', wildcard="Images (*.*.img)|*.img", style=wx.FD_OPEN) as fileDialog:
            puml(":Select boot image to patch;\n")
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                print("User cancelled backup creation.")
                puml("#:User Cancelled;\n}\n")
                return
            # save the current contents in the file
            file_to_patch = fileDialog.GetPath()
            file_sha1 = sha1(file_to_patch)
            print(f"\nSelected {file_to_patch} for patching with SHA1 of {file_sha1}")
            puml(f"note right\nSelected {file_to_patch} for patching with SHA1 of {file_sha1}\nend note\n")
    else:
        # Make sure boot image is selected
        if not self.config.boot_id:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Select a boot image.")
            print("Aborting ...\n")
            puml("#red:Valid boot image is not selected;\n}\n")
            return

    # Make sure platform-tools is set and adb and fastboot are found
    if not self.config.platform_tools_path:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Select Android Platform Tools (ADB)")
        print("Aborting ...\n")
        puml("#red:Valid Anroid Platform Tools is not selected;\n}\n")
        return

    # Make sure the phone is in adb mode.
    if device.mode != 'adb':
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Device: {device.id} is not in adb mode.")
        print("Perhaps a Scan is necessary?")
        print("Aborting ...\n")
        puml("#red:Device is not in ADB mode;\n}\n")
        return

    start = time.time()

    if custom_patch:
        boot_path = file_to_patch
        boot_file_name = os.path.basename(boot_path)
        filename, extension = os.path.splitext(boot_file_name)
        stock_sha1 = file_sha1[:8]
        boot_img = f"{filename}_{stock_sha1}.img"
        magisk_patched_img = f"magisk_patched_{file_sha1[:8]}.img"
    else:
        boot = get_boot()
        boot_path = boot.boot_path
        boot_file_name = os.path.basename(boot_path)
        stock_sha1 = boot.boot_hash[:8]
        boot_img = f"{boot_file_name}_{stock_sha1}.img"
        magisk_patched_img = f"magisk_patched_{boot.boot_hash[:8]}.img"
    config_path = get_config_path()
    boot_images = os.path.join(config_path, get_boot_images_dir())
    tmp_dir_full = os.path.join(config_path, 'tmp')

    # delete all files in tmp folder to make sure we're dealing with new files only.
    delete_all(tmp_dir_full)

    # check if boot_file_name got extracted (if not probably the zip does not have it)
    if not os.path.exists(boot_path):
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You have selected the Patch option, however boot file is not found.")
        puml("#red:Cannot patch an already patched file;\n")
        print("Aborting ...\n}\n")
        return

    if not custom_patch:
        # Extract phone model from boot.package_sig and warn the user if it is not from the current phone model
        package_sig = boot.package_sig.split("-")
        try:
            firmware_model = package_sig[0]
        except Exception as e:
            firmware_model = None
        if firmware_model != device.hardware:
            title = "Boot Model Mismatch"
            message =  f"WARNING: Your phone model is: {device.hardware}\n\n"
            message += f"The selected {boot_file_name} is from: {boot.package_sig}\n\n"
            message += f"Please make sure the {boot_file_name} file you are trying to patch,\n"
            message += f"is for the selected device: {device.id}\n\n"
            message += "Click OK to accept and continue.\n"
            message += "or Hit CANCEL to abort."
            print(f"\n*** Dialog ***\n{message}\n______________\n")
            puml("#orange:WARNING;\n", True)
            puml(f"note right\n{message}\nend note\n")
            dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                print("User pressed ok.")
                puml(":User Pressed OK to continue;\n")
            else:
                print("User pressed cancel.")
                puml("#pink:User Pressed Cancel to abort;\n}\n")
                print("Aborting ...\n")
                return

    # delete existing boot_img from phone
    res = device.delete(f"{self.config.phone_path}/{boot_img}")
    if res != 0:
        print("Aborting ...\n")
        puml("#red:Failed to delete old boot image from the phone;\n}\n")
        return

    # check if delete worked.
    print("Making sure file is not on the phone ...")
    res, tmp = device.check_file(f"{self.config.phone_path}/{boot_img}")
    if res != 0:
        print("Aborting ...\n")
        puml("#red:Failed to delete old boot image from the phone;\n}\n")
        return

    # delete existing magisk_patched from phone
    res = device.delete(f"{self.config.phone_path}/magisk_patched*.img")
    if res != 0:
        puml("#red:Failed to delete old magisk_patched.img;\n")
        print("Aborting ...\n}\n")
        return

    # check if delete worked.
    print("Making sure file is not on the phone ...")
    res, tmp = device.check_file(f"{self.config.phone_path}/magisk_patched*.img")
    if res != 0:
        puml("#red:Failed to delete old magisk_patched.img;\n")
        print("Aborting ...\n}\n")
        return

    # Transfer boot image to the phone
    res = device.push_file(f"{boot_path}", f"{self.config.phone_path}/{boot_img}")
    if res != 0:
        puml("#red:Failed to transfer the boot file to the phone;\n")
        print("Aborting ...\n}\n")
        return

    # check if transfer worked.
    res, tmp = device.check_file(f"{self.config.phone_path}/{boot_img}")
    if res != 1:
        print("Aborting ...\n")
        puml("#red:Failed to transfer the boot file to the phone;\n}\n")
        return

    #------------------------------------
    # Check to see if Magisk is installed
    #------------------------------------
    print("Looking for Magisk Manager app ...")
    puml(":Checking Magisk Manager;\n")
    magisk_app_version = device.get_uncached_magisk_app_version()
    magisk_version = device.magisk_version
    is_rooted = device.rooted

    # If the device is not reporting rooted, and adb shell access is not granted
    # Display a warning and abort.
    if self.config.magisk != '' and self.config.magisk not in ['com.topjohnwu.magisk', 'io.github.vvb2060.magisk', 'io.github.huskydg.magisk'] and not is_rooted:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: It looks like you have a hidden Magisk Manager, and have not allowed root access to adb shell")
        print("Patching can not be performed, to correct this, either grant root access to adb shell (recommended) or unhide Magisk Manager.")
        print("And try again.")
        print("Aborting ...\n")
        puml("#red:Hidden Magisk and root isnot granted;\n}\n")
        return

    # ==========================================
    # Sub Function       patch_script
    # ==========================================
    def patch_script(patch_method):
        print("Creating pf_patch.sh script ...")
        if patch_method == "rooted":
            patch_label = "rooted Magisk"
            script_path = "/data/adb/magisk/pf_patch.sh"
            exec_cmd = f"\"{get_adb()}\" -s {device.id} shell \"su -c \'cd /data/adb/magisk; ./pf_patch.sh\'\""
            with_version = device.magisk_version
            with_version_code = device.magisk_version_code
        elif patch_method == "app":
            patch_label = "Magisk App"
            path_to_busybox = os.path.join(get_bundle_dir(),'bin', f"busybox_{device.architecture}")
            script_path = "/data/local/tmp/pf_patch.sh"
            exec_cmd = f"\"{get_adb()}\" -s {device.id} shell /data/local/tmp/pf_patch.sh"
            with_version = device.get_uncached_magisk_app_version()
            with_version_code = device.magisk_app_version_code
        else:
            print(f"ERROR: Unsupport patch method: {patch_method}")
            return -1

        set_patched_with(with_version)
        puml(f":Patching with {patch_label}: {with_version};\n", True)

        dest = os.path.join(config_path, 'tmp', 'pf_patch.sh')
        with open(dest.strip(), "w", encoding="ISO-8859-1", errors="replace", newline='\n') as f:
            data = " #!/system/bin/sh\n"
            data += " ##############################################################################\n"
            data += f" # PixelFlasher {VERSION} patch script using {patch_label} {with_version}\n"
            data += " ##############################################################################\n"
            data += f"MAGISK_VERSION=\"{with_version_code}\"\n"
            data += f"STOCK_SHA1={stock_sha1}\n"

            if patch_method == "app":
                data += f"ARCH={device.architecture}\n"
                data += f"cp {device.magisk_path} /data/local/tmp/pf.zip\n"
                data += "cd /data/local/tmp\n"
                data += "rm -rf pf\n"
                data += "mkdir pf\n"
                data += "cd pf\n"
                data += "../busybox unzip -o ../pf.zip\n"
                data += "cd assets\n"
                data += "for FILE in ../lib/$ARCH/lib*.so; do\n"
                data += "    NEWNAME=$(echo $FILE | sed -En 's/.*\/lib(.*)\.so/\\1/p')\n"
                data += "    cp $FILE $NEWNAME\n"
                data += "done\n"
                if device.architecture == "x86_64":
                    data += "cp ../lib/x86/libmagisk32.so magisk32\n"
                elif device.architecture == "arm64-v8a" and (device.ro_zygote != "zygote64" or "zygote64_32" in with_version.lower()):
                    data += "cp ../lib/armeabi-v7a/libmagisk32.so magisk32\n"
                data += "chmod 755 *\n"

            data += "SYSTEM_ROOT=false\n"
            data += "grep \' / \' /proc/mounts | grep -qv \'rootfs\' && SYSTEM_ROOT=true\n"
            data += ". ./util_functions.sh\n"
            data += 'get_flags\n'
            data += "echo -------------------------\n"
            data += "echo \"SYSTEM_ROOT:       $SYSTEM_ROOT\"\n"
            data += "echo \"KEEPVERITY:        $KEEPVERITY\"\n"
            data += "echo \"KEEPFORCEENCRYPT:  $KEEPFORCEENCRYPT\"\n"
            data += "echo \"RECOVERYMODE:      $RECOVERYMODE\"\n"
            data += "echo \"PATCHVBMETAFLAG:   $PATCHVBMETAFLAG\"\n"
            data += "echo \"ISENCRYPTED:       $ISENCRYPTED\"\n"
            data += "echo \"VBMETAEXIST:       $VBMETAEXIST\"\n"
            data += "export KEEPVERITY KEEPFORCEENCRYPT RECOVERYMODE PATCHVBMETAFLAG ISENCRYPTED VBMETAEXIST SYSTEM_ROOT\n"
            data += "echo -------------------------\n"
            data += "echo \"Creating a patch ...\"\n"
            data += "./magiskboot cleanup\n"
            data += f"./boot_patch.sh /sdcard/Download/{boot_img}\n"
            data += "PATCH_SHA1=$(./magiskboot sha1 new-boot.img | cut -c-8)\n"
            data += "echo \"PATCH_SHA1:     $PATCH_SHA1\"\n"
            data += "PATCH_FILENAME=magisk_patched_${MAGISK_VERSION}_${STOCK_SHA1}_${PATCH_SHA1}.img\n"
            data += "echo \"PATCH_FILENAME: $PATCH_FILENAME\"\n"
            data += "echo $PATCH_FILENAME > /data/local/tmp/pf_patch.log\n"

            if patch_method == "app":
                data += "cp -f /data/local/tmp/pf/assets/new-boot.img /sdcard/Download/${PATCH_FILENAME}\n"

                # if we're rooted, copy the stock boot.img to /data/adb/magisk/stock_boot.img so that magisk can backup
                if is_rooted:
                    data += "cp -f /data/local/tmp/pf/assets/stock_boot.img /data/adb/magisk/stock_boot.img\n"
                    # TODO see if we need to update the config SHA1
            else:
                data += "mv new-boot.img /sdcard/Download/${PATCH_FILENAME}\n"

            f.write(data)
            puml(f"note right\nPatch Script\n====\n{data}end note\n")

        print("PixelFlasher patching script contents:")
        print(f"___________________________________________________\n{data}")
        print("___________________________________________________\n")

        # Transfer extraction script to the phone
        res = device.push_file(f"{dest}", script_path, is_rooted)
        if res != 0:
            print("Aborting ...\n")
            puml("#red:Failed to transfer Patch Script to the phone;\n")
            return -1

        # set the permissions.
        res = device.set_file_permissions(script_path, "755", is_rooted)
        if res != 0:
            print("Aborting ...\n")
            puml("#red:Failed to set the executable bit on patch script;\n")
            return -1

        if patch_method == "app":
            # Transfer busybox to the phone
            res = device.push_file(f"{path_to_busybox}", "/data/local/tmp/busybox")
            if res != 0:
                print("Aborting ...\n")
                puml("#red:Failed to transfer busybox to the phone;\n")
                return -1

            # set the permissions.
            res = device.set_file_permissions("/data/local/tmp/busybox", "755")
            if res != 0:
                print("Aborting ...\n")
                puml("#red:Failed to set the executable bit on busybox;\n")
                return -1

        #------------------------------------
        # Execute the pf_patch.sh script
        #------------------------------------
        print("Executing the pf_patch.sh script ...")
        print(f"PixelFlasher Patching phone with {patch_label}: {with_version}")
        puml(":Executing the patch script;\n")
        res = run_shell2(exec_cmd)

        # get the patched_filename
        print("Checking patch log: /data/local/tmp/pf_patch.log ...")
        res = device.file_content("/data/local/tmp/pf_patch.log")
        if res == -1:
            print("Aborting ...\n")
            puml("#red:Failed to pull pf_patch.log from the phone;\n")
            return -1
        else:
            magisk_patched_img = res.strip('\n')

        # delete pf_patch.log from phone
        res = device.delete("/data/local/tmp/pf_patch.log", is_rooted)
        if res != 0:
            print("Aborting ...\n")
            puml("#red:Failed to delete pf_patch.log from the phone;\n")
            return -1

        return magisk_patched_img

    # -------------------------------
    # Patching decision
    # -------------------------------
    if is_rooted:
        if not magisk_app_version:
            magisk_patched_img = patch_script("rooted")
            if magisk_patched_img == -1:
                print("Aborting ...\n")
                puml("#red:Failed to patch\n}\n", True)
                return
        elif magisk_version and magisk_app_version:
            m_version = 0
            m_app_version = 0
            with contextlib.suppress(Exception):
                m_version = magisk_version.split(':')[1]
                m_app_version = magisk_app_version.split(':')[1]
            print(f"  Magisk Manager Version: {m_app_version}")
            print(f"  Magisk Version:         {m_version}")
            puml(f"note right\nMagisk Manager Version: {m_app_version}\nMagisk Version:         {m_version}\nend note\n")
            if magisk_version != magisk_app_version:
                # TODO check if Magisk Manager is a stub, which would have 1.0.1 version
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} WARNING: Magisk Version is different than Magisk Manager version")
                puml("#orange:WARNING: Magisk Version is different than Magisk Manager version;\n")
                if m_version >= m_app_version:
                    magisk_patched_img = patch_script("rooted")
                else:
                    magisk_patched_img = patch_script("app")
            else:
                magisk_patched_img = patch_script("rooted")
            if magisk_patched_img == -1:
                print("Aborting ...\n")
                puml("#red:Failed to patch\n}\n", True)
                return
    elif magisk_app_version:
        magisk_patched_img = patch_script("app")
        if magisk_patched_img == -1:
            print("Aborting ...\n")
            puml("#red:Failed to patch\n}\n", True)
            return
    else:
        # Device is not rooted
        print("Unable to find magisk on the phone, perhaps it is hidden?")
        puml("#orange:Magisk not found;\n")
        # Message to Launch Manually and Patch
        title = "Magisk Manager is not detected."
        message =  f"WARNING: Magisk Manager [{get_magisk_package()}] is not found on the phone\n\n"
        message += "This could be either because it is hidden, or it is not installed (most likely not installed)\n\n"
        message += "If it is installed and hidden, then you should abort and then unhide it.\n"
        message += "If Magisk is not installed, PixelFlasher can install it for you and use it for patching.\n\n"
        message += "WARNING: Do not install Magisk again if it is currently hidden.\n"
        message += "Do you want PixelFlasher to download and install Magisk?\n"
        message += "You will be given a choice of Magisk Version to install.\n\n"
        message += "Click OK to continue with Magisk installation.\n"
        message += "or Hit CANCEL to abort."
        print(f"\n*** Dialog ***\n{message}\n______________\n")
        puml(f"note right\nDialog\n====\n{message}\nend note\n")
        dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            # ok to download and install
            print("User pressed ok.")
            puml(":User Pressed OK;\nnote right:Proceed to Magisk download and install\n")
            dlg = MagiskDownloads(self)
            dlg.CentreOnParent(wx.BOTH)
            result = dlg.ShowModal()
            if result != wx.ID_OK:
                # User cancelled out of Magisk Installation
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Cancel, out of Magisk download and install.")
                puml(":User Pressed Cancel;\n}\n")
                print("Aborting ...\n")
                dlg.Destroy()
                return
            dlg.Destroy()
            try:
                magisk_app_version = device.get_uncached_magisk_app_version()
                if magisk_app_version:
                    # Magisk Manager is installed
                    print(f"Found Magisk Manager version {magisk_app_version} on the phone.")
                    puml(f":Found Magisk Manager;\nnote right:version {magisk_app_version}\n", True)
                    # continue with patching using Magisk Manager.
                    magisk_patched_img = patch_script("app")
                    if magisk_patched_img == -1:
                        print("Aborting ...\n")
                        puml("#red:Failed to patch\n}\n", True)
                        return
                else:
                    print("Magisk Manager is still not detected.\n\Aborting ...\n")
                    puml("#red:Magisk Manager is still not detected;\nnote right:Abort\n}\n", True)
                    return
            except Exception:
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Failed Magisk is still not detected.")
                puml("#red:Magisk Manager is still not detected;\nnote right:Abort\n}\n", True)
                print("Aborting ...\n")
                return
        else:
            # not ok to download and install, (Magisk is hidden option)
            print("User pressed cancel for downloading and installing Magisk.")
            puml(":User Pressed Cancel;\n}\n")
            print("Aborting ...\n")
            return

    # -------------------------------
    # Validation Checks
    # -------------------------------
    # abort if patching failed
    if magisk_patched_img == -1:
        puml("}\n")
        return

    # check if magisk_patched_img got created.
    print(f"\nLooking for {magisk_patched_img} in {self.config.phone_path} ...")
    res, magisk_patched = device.check_file(f"{self.config.phone_path}/{magisk_patched_img}")
    if res != 1:
        print("Aborting ...\n")
        puml("#red:Failed to find magisk_patched on the phone;\n}\n")
        return

    # Transfer back magisk_patched.img
    print(f"Pulling {magisk_patched} from the phone to: {magisk_patched_img} ...")
    magisk_patched_img_file = os.path.join(tmp_dir_full, magisk_patched_img)
    res = device.pull_file(magisk_patched, f"\"{magisk_patched_img_file}\"")
    if res != 0:
        print("Aborting ...\n")
        puml("#red:Failed to pull magisk_patched from the phone;\n}\n")
        return

    # get the checksum of the magisk_patched.img
    print(f"Getting SHA1 of {magisk_patched_img_file} ...")
    checksum = sha1(os.path.join(magisk_patched_img_file))
    print(f"SHA1 of {magisk_patched_img} file: {checksum}")

    # get source boot_file_name sha1
    print(f"\nGetting SHA1 of source {boot_file_name} ...")
    boot_sha1_long = sha1(boot_path)
    boot_sha1 = boot_sha1_long[:8]
    print(f"Source {boot_file_name}'s SHA1 is: {boot_sha1_long}")

    # check to make sure the patch sha1 is not the same as the source (stock) sha1
    if checksum == boot_sha1_long:
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Patching failed, magisk_patched SHA1 is the same as the stock SHA1")
        puml("#red:Patching failed;\nnote right:magisk_patched SHA1 is the same as the stock SHA1\n}\n", True)
        print("Aborting ...\n")
        return

    # if rooted, get magisk's stored sha1 from it's config.
    if is_rooted:
        print("Getting SHA1 from Magisk config ...")
        magisk_sha1 = device.magisk_sha1
        print(f"Magisk Config's SHA1 is:   {magisk_sha1}")
        # compare it to the original boot_file_name file's sha1
        # print(f"Comparing source {boot_file_name} SHA1 with Magisk's config SHA1 (they should match) ...")
        # if boot_sha1_long != magisk_sha1:
        #     print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} WARNING: Something is wrong Magisk config has the wrong SHA1 ...")
        #     # fix it
        #     # res = device.update_magisk_config(boot_sha1_long)
        # else:
        #     print(f"Good: Both SHA1s: {boot_sha1_long} match.")
        # see if we have a Magisk backup
        print(f"\nChecking to see if Magisk made a backup of the source {boot_file_name}")
        magisk_backups = device.magisk_backups
        if magisk_backups and boot_sha1_long in magisk_backups:
            print("Good: Magisk has made a backup")
            puml("#lightgreen:Magisk Backup: Success;\n")
        else:
            print(f"Magisk has NOT made a backup of the source {boot_file_name}")
            print("Triggering Magisk to create a backup ...")
            # Trigger Magisk to make a backup
            res = device.run_magisk_migration(boot_sha1_long)
            # if return is -2, then copy boot.img to stock_boot.img
            if res == -2 and is_rooted:
                # copy stock_boot from Downloads folder it already exists, and do it as su if rooted
                stock_boot_path = '/data/adb/magisk/stock_boot.img'
                print(f"Copying {boot_img} to {stock_boot_path} ...")
                res = device.su_cp_on_device(f"/sdcard/Download/{boot_img}", stock_boot_path)
                if res != 0:
                    print("Aborting Backup ...\n")
                else:
                    # rerun the migration.
                    print("Triggering Magisk migration again to create a backup ...")
                    res = device.run_magisk_migration(boot_sha1_long)
                    print(f"\nChecking to see if Magisk made a backup of the source {boot_file_name}")
                    magisk_backups = device.magisk_backups
                    if magisk_backups and boot_sha1_long in magisk_backups:
                        print("Good: Magisk has made a backup")
                        puml("#lightgreen:Magisk Backup: Success;\n")
                    else:
                        print("It looks like backup was not made.")

    # Extract sha1 from the patched image
    print(f"\nExtracting short SHA1 from {magisk_patched_img} ...")
    puml(f":Extract SHA1 from {magisk_patched_img};\n", True)
    patched_sha1 = extract_sha1(magisk_patched_img_file)
    if patched_sha1:
        print(f"Short SHA1 embedded in {magisk_patched_img_file} is: {patched_sha1}")
        print(f"Comparing short source {boot_file_name} SHA1 with short SHA1 embedded in {patched_sha1} (they should match) ...")
        if patched_sha1 != boot_sha1:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Something is wrong with the patched file.")
            print(f"                           {magisk_patched_img} extracted sha1: {patched_sha1}")
            print(f"                           {boot_file_name} sha1:                     {boot_sha1}")
            print("                           They don't match.\nAborting\n")
            puml(f"#red:ERROR: Something is wrong with the patched file\nSHA1: {patched_sha1}\nExpected SHA1: {boot_sha1};\n", True)
            return
        else:
            print(f"Good: Both SHA1s: {patched_sha1} match.\n")
            puml(f"note right:SHA1 {patched_sha1} matches the expected value\n")
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} NOTICE: The patched image file does not contain source boot's SHA1")
        print("                            This is normal for older devices, but newer deviced should have it.")
        print("                            If you have a newer device, please double check if everything is ok.\n ")
        puml("#orange:The patched image file does not contain source boot's SHA1;\n")
        puml(f"note right\nThis is normal for older devices, but newer deviced should have it.\nend note\n")


    if not custom_patch:
        # if a matching magisk_patched.img is not found, store it.
        cached_boot_img_dir_full = os.path.join(boot_images, boot.boot_hash)
        cached_boot_img_path = os.path.join(cached_boot_img_dir_full, magisk_patched_img)
        debug(f"Checking for cached copy of {boot_file_name}")
        if not os.path.exists(cached_boot_img_path):
            debug(f"Cached copy of {magisk_patched_img} with sha1: {checksum} is not found.")
            debug(f"Copying {magisk_patched_img_file} to {cached_boot_img_dir_full}")
            shutil.copy(magisk_patched_img_file, cached_boot_img_dir_full, follow_symlinks=True)
        else:
            debug(f"Found a cached copy of magisk_patched.img sha1={checksum}\n")

        # create BOOT db record
        con = get_db()
        con.execute("PRAGMA foreign_keys = ON")
        con.commit()
        cursor = con.cursor()
        sql = 'INSERT INTO BOOT (boot_hash, file_path, is_patched, magisk_version, hardware, epoch) values(?, ?, ?, ?, ?, ?) ON CONFLICT (boot_hash) DO NOTHING'
        data = (checksum, cached_boot_img_path, 1, get_patched_with(), device.hardware, time.time())
        debug(f"Creating BOOT record, boot_hash: {checksum}")
        try:
            cursor.execute(sql, data)
            con.commit()
            boot_id = cursor.lastrowid
            debug(f"DB BOOT record ID: {boot_id}")
        except Exception as e:
            boot_id = 0
        # if we didn't insert in BOOT, see if we have a record for the boot being processed in case we need to insert a record into PACKAGE_BOOT
        if boot_id == 0:
            cursor.execute(f"SELECT ID FROM BOOT WHERE boot_hash = '{checksum}'")
            data = cursor.fetchall()
            if len(data) > 0:
                boot_id = data[0][0]
                debug(f"Found a previous BOOT record id={boot_id} for boot_hash: {checksum}\n")
            else:
                boot_id = 0
                debug(f"ERROR: Something went wrong while inserting BOOT record id={boot_id} for boot_hash: {checksum}\n")

        # create PACKAGE_BOOT db record
        if boot.package_id > 0 and boot_id > 0:
            debug(f"Creating PACKAGE_BOOT record, package_id: {boot.package_id} boot_id: {boot_id}")
            sql = 'INSERT INTO PACKAGE_BOOT (package_id, boot_id, epoch) values(?, ?, ?) ON CONFLICT (package_id, boot_id) DO NOTHING'
            data = (boot.package_id, boot_id, time.time())
            try:
                cursor.execute(sql, data)
                con.commit()
                package_boot_id = cursor.lastrowid
                debug(f"DB Package_Boot record ID: {package_boot_id}\n")
            except Exception as e:
                package_boot_id = 0

        set_db(con)
    else:
        # Display save as dialog to save the patched file
        with wx.FileDialog(self, "Save Patched Magisk File", '', f"{magisk_patched_img}", wildcard="Image files (*.img)|*.img", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                print(f"User Cancelled saving: {magisk_patched_img}")
                return     # the user changed their mind
            shutil.copy(magisk_patched_img_file, fileDialog.GetPath(), follow_symlinks=True)

    end = time.time()
    print(f"\nMagisk Version: {get_patched_with()}")
    print(f"Patch time: {math.ceil(end - start)} seconds")
    print("------------------------------------------------------------------------------\n")
    puml(f"#cee7ee:End {custom_text}Patching;\n", True)
    puml(f"note right:Patch time: {math.ceil(end - start)} seconds\n")
    puml("}\n")

    populate_boot_list(self)


# ============================================================================
#                               Function live_flash_boot_phone
# ============================================================================
def live_flash_boot_phone(self, option):
    puml(f"#cyan:{option} Boot;\n", True)
    puml(f"partition \"**{option} Boot**\"")
    puml(" {\n")
    if not get_adb():
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Android Platform Tools must be set.")
        puml("#red:Valid Anroid Platform Tools is not selected;\n}\n")
        return

    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You must first select a valid device.")
        puml("#red:Valid device is not selected;\n}\n")
        return

    if device.hardware in ('panther', 'cheetah') and option == 'Live':
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Live booting Pixel 7 or Pixel 7p is not supported yet.")
        puml("#red:Live booting Pixel 7 or Pixel 7p is not supported yet;\n}\n")
        return

    boot = get_boot()
    if boot:
        if boot.is_patched:
            firmware_model = boot.hardware
        else:
            # Extract phone model from boot.package_sig
            package_sig_array = boot.package_sig.split("-")
            try:
                firmware_model = package_sig_array[0]
            except Exception as e:
                firmware_model = None
        # Warn the user if it is not from the current phone model
        if firmware_model != device.hardware:
            title = f"{option} Boot"
            message =  f"ERROR: Your phone model is: {device.hardware}\n\n"
            message += f"The selected Boot is for: {boot.hardware}\n\n"
            message += "Unless you know what you are doing, if you continue flashing\n"
            message += "you risk bricking your device, proceed only if you are absolutely\n"
            message += "certian that this is what you want, you have been warned.\n\n"
            message += "Click OK to accept and continue.\n"
            message += "or Hit CANCEL to abort."
            print(f"\n*** Dialog ***\n{message}\n______________\n")
            puml("#orange:WARNING;\n", True)
            puml(f"note right\n{message}\nend note\n")
            dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                print("User pressed ok.")
                puml(":User Pressed OK to continue;\n")
            else:
                print("User pressed cancel.")
                puml("#pink:User Pressed Cancel to abort;\n}\n")
                print("Aborting ...\n")
                return
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to access boot object, aborting ...\n")
        puml("#red:Unable to access boot object\n}\n")
        return

    # Make sure boot exists
    if boot.boot_path:
        title = f"{option} Boot"
        message  = f"Live/Flash Boot Options:\n\n"
        message += f"Option:                 {option}\n"
        message += f"Boot Hash:              {boot.boot_hash}\n"
        message += f"Hardware:               {device.hardware}\n"
        if boot.is_patched == 1:
            message += "Patched:                Yes\n"
            message += f"With Magisk:            {boot.magisk_version}\n"
            message += f"Original boot.img from: {boot.package_sig}\n"
            message += f"Original boot.img Hash: {boot.package_boot_hash}\n"
        else:
            message += "Patched:                No\n"
        message += f"Custom Flash Options:   {self.config.advanced_options}\n"
        # don't allow inactive slot flashing
        message += "Flash To Inactive Slot: False\n"
        message += f"Flash Both Slots:       {self.config.flash_both_slots}\n"
        message += f"Verbose Fastboot:       {self.config.fastboot_verbose}\n"
        message += "boot.img path:\n"
        message += f"  {boot.boot_path}\n"
        message += "\nClick OK to accept and continue.\n"
        message += "or Hit CANCEL to abort."
        print(f"\n*** Dialog ***\n{message}\n______________\n")
        puml(f":{option} Boot;\n", True)
        puml(f"note right\nDialog\n====\n{message}\nend note\n")
        set_message_box_title(title)
        set_message_box_message(message)
        dlg = MessageBox(self)
        dlg.CentreOnParent(wx.BOTH)
        result = dlg.ShowModal()
        if result == wx.ID_OK:
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Ok.")
            puml(":User Pressed OK to continue;\n")
        else:
            print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Cancel.")
            puml("#pink:User Pressed Cancel to abort;\n}\n")
            print("Aborting ...\n")
            dlg.Destroy()
            return
        dlg.Destroy()
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to get boot.img path, aborting ...\n")
        puml("#red:Unable to get boot image path;\n}\n")
        return

    if device.mode == 'adb':
        device.reboot_bootloader()
        print("Waiting 10 seconds ...")
        puml(":Sleep 10 seconds;\n")
        time.sleep(10)
        self.device_choice.SetItems(get_connected_devices())
        self._select_configured_device()

    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to detect the device.")
        print("You can try scanning for devices and selecting your device (it should be in bootloader mode).")
        print(f"and then press the same {option} button again.")
        puml("#red:Valid device is not detected;\n")
        puml(f"note right\nYou can try scanning for devices and selecting your device (it should be in bootloader mode).\nand then press the same {option} button again.\nend note\n")
        puml("}\n")
        return

    if device.mode == 'f.b' and get_fastboot():
        startFlash = time.time()
        print("")
        print("==============================================================================")
        print(f" {datetime.now():%Y-%m-%d %H:%M:%S} PixelFlasher {VERSION}              Flashing / Live Booting\n     {boot.boot_path} ...")
        print("==============================================================================")
        puml(":Flashing / Live Booting;\n", True)
        puml(f"note right:File: {boot.boot_path};\n")
        # if device.hardware in ('panther', 'cheetah'):
        #     # Pixel 7 and 7P need a special command to Live Boot.
        #     # https://forum.xda-developers.com/t/td1a-220804-031-factory-image-zip-is-up-unlock-bootloader-root-pixel-7-pro-cheetah-limited-safetynet-all-relevant-links.4502805/post-87571843
        #     kernel = os.path.join(os.path.dirname(boot.boot_path), "boot.img")
        #     if os.path.exists(kernel):
        #         theCmd = f"\"{get_fastboot()}\" -s {device.id} boot \"{kernel}\" \"{boot.boot_path}\""
        #     else:
        #         print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Missing Kernel {kernel} ...\n")
        #         print(f"Aborting ...\n")
        #         return
        # else:
        fastboot_options = ''
        slot = ''
        if option == 'Flash':
            # don't allow inactive slot flashing
            # if self.config.flash_to_inactive_slot:
            #     fastboot_options += '--slot other '
            if self.config.advanced_options:
                if self.config.flash_both_slots:
                    fastboot_options += '--slot all '
                if self.config.fastboot_verbose:
                    fastboot_options += '--verbose '
            fastboot_options += 'flash '
        if device.hardware in ('panther', 'cheetah'):
            theCmd = f"\"{get_fastboot()}\" -s {device.id} {fastboot_options} init_boot \"{boot.boot_path}\""
        else:
            theCmd = f"\"{get_fastboot()}\" -s {device.id} {fastboot_options} boot \"{boot.boot_path}\""
        debug(theCmd)
        res = run_shell(theCmd)
        if res.returncode != 0:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: {option} boot failed!")
            print(f"Return Code: {res.returncode}.")
            print(f"Stdout: {res.stdout}.")
            print(f"Stderr: {res.stderr}.")
            print("Aborting ...\n")
            puml("#red:{option} Boot failed!;\n}\n")
            puml("}\n")
            return
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Done!")
        endFlash = time.time()
        print(f"Flashing elapsed time: {math.ceil(endFlash - startFlash)} seconds")
        print("------------------------------------------------------------------------------\n")
        done_flashing = True
        # clear the selected device option
        set_phone(None)
        self.device_label.Label = "ADB Connected Devices"
        self.config.device = None
        self.device_choice.SetItems([''])
        self.device_choice.Select(0)
        # Live automatically reboots, so we can only control the Flash one.
        if option == 'Flash' and not self.config.no_reboot:
            puml(":Reboot to System;\n")
            device.reboot_system()
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Device {device.id} not in bootloader mode.")
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Aborting ...\n")
        puml("#red:Device is not in bootloader mode;\n}\n")

    puml(f"#cee7ee:End {option} Boot;\n", True)
    if done_flashing:
        puml(f"note right:Flashing elapsed time: {math.ceil(endFlash - startFlash)} seconds\n")
    puml("}\n")
    return


# ============================================================================
#                               Function flash_phone
# ============================================================================
def flash_phone(self):
    puml("#cyan:Flash Firmware;\n", True)
    puml("partition \"**Flash Firmware**\" {\n")
    if not get_adb():
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Android Platform Tools must be set.")
        puml("#red:Android Platform Tools is not set;\n}\n")
        return

    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You must first select a valid adb device.")
        puml("#red:Valid device is not selected;\n}\n")
        return

    cwd = os.getcwd()
    config_path = get_config_path()
    factory_images = os.path.join(config_path, 'factory_images')

    if self.config.advanced_options and self.config.flash_mode == 'customFlash':
        image_mode = get_image_mode()
        package_dir_full = os.path.join(config_path, 'tmp')
    else:
        package_sig = get_firmware_id()
        if not package_sig:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: You must first select a factory firmware file.")
            puml("#red:Factory firmware is not selected;\n}\n")
            return

        if get_firmware_model() in ['raven', 'oriole', 'bluejay'] and device.api_level and int(device.api_level) < 33:
            if not (self.config.advanced_options and self.config.flash_both_slots):
                title = "Tensor device not on Android 13 or higher"
                message =  f"WARNING: Your phone OS version is lower than Android 13.\n\n"
                message += f"If you are upgrading to Android 13 or newer,\n"
                message += "make sure you at least flash the bootloader to both slots.\n"
                message += "The Android 13 update for Pixel 6, Pixel 6 Pro, and the Pixel 6a contains\n"
                message += "a bootloader update that increments the anti-roll back version for the bootloader.\n"
                message += "This prevents the device from rolling back to previous vulnerable versions of the bootloader.\n"
                message += "After flashing an Android 13 build on these devices\n"
                message += "you will not be able to flash and boot older Android 12 builds.\n\n"
                message += "Selecting the option 'Flash to both slots'\n"
                message += "Will take care of that.\n\n"
                message += "Click OK to continue as is.\n"
                message += "or Hit CANCEL to abort and change options."
                puml(":API < 33 and device is Tensor;\n")
                puml(f"note right\nDialog\n====\n{message}\nend note\n")
                print(f"\n*** Dialog ***\n{message}\n______________\n")
                dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
                result = dlg.ShowModal()
                if result == wx.ID_OK:
                    print("User pressed ok.")
                    puml(":User Pressed OK;\n")
                else:
                    print("User pressed cancel.")
                    print("Aborting ...\n")
                    puml("#pink:User Pressed Cancel to abort;\n}\n")
                    return

        package_dir_full = os.path.join(factory_images, package_sig)
        boot = get_boot()

    message = ''

    # if advanced options is set, and we have flash options ...
    fastboot_options = ''
    fastboot_options2 = ''
    if self.config.advanced_options:
        if self.config.flash_both_slots:
            fastboot_options += '--slot all '
        if self.config.disable_verity:
            fastboot_options += '--disable-verity '
            fastboot_options2 += '--disable-verity '
        if self.config.disable_verification:
            fastboot_options += '--disable-verification '
            fastboot_options2 += '--disable-verification '
        if self.config.fastboot_verbose:
            fastboot_options += '--verbose '
            fastboot_options2 += '--verbose '
        if self.config.fastboot_force:
            fastboot_options2 += '--force '
        message  = f"Custom Flash Options:   {self.config.advanced_options}\n"
        if self.config.flash_mode == 'customFlash' and image_mode == 'SIDELOAD':
            message  = "   ATTENTION!           Flash Options Don\'t apply to Sideloading.\n"
        else:
            message  = f"Custom Flash Options:   {self.config.advanced_options}\n"
            message += f"Disable Verity:         {self.config.disable_verity}\n"
            message += f"Disable Verification:   {self.config.disable_verification}\n"
            message += f"Flash Both Slots:       {self.config.flash_both_slots}\n"
            message += f"Force:                  {self.config.fastboot_force}\n"
            message += f"Verbose Fastboot:       {self.config.fastboot_verbose}\n"
            message += f"Temporary Root:         {self.config.temporary_root}\n"
    message += f"Flash To Inactive Slot: {self.config.flash_to_inactive_slot}\n"

    if sys.platform == "win32":
        flash_pf_file = os.path.join(package_dir_full, "flash-pf.bat")
        if self.config.force_codepage:
            cp = str(self.config.custom_codepage)
            if cp == '':
                cp = None
        else:
            cp = get_system_codepage()
        if cp:
            first_line = f"chcp {cp}\n@ECHO OFF\n"
        else:
            first_line = f"@ECHO OFF\n"
        if self.config.advanced_options and self.config.flash_mode == 'customFlash':
            version_sig = f":: This is a generated file by PixelFlasher v{VERSION}\n:: cd {package_dir_full}\n:: Android Platform Tools Version: {get_sdk_version()}\n\n"
        else:
            version_sig = f":: This is a generated file by PixelFlasher v{VERSION}\n:: cd {package_dir_full}\n:: pf_boot.img: {boot.boot_path}\n:: Android Platform Tools Version: {get_sdk_version()}\n\n"
    else:
        flash_pf_file = os.path.join(package_dir_full, "flash-pf.sh")
        first_line = "#!/bin/sh\n"
        if self.config.advanced_options and self.config.flash_mode == 'customFlash':
            version_sig = f"# This is a generated file by PixelFlasher v{VERSION}\n# cd {package_dir_full}\n# Android Platform Tools Version: {get_sdk_version()}\n\n"
        else:
            version_sig = f"# This is a generated file by PixelFlasher v{VERSION}\n# cd {package_dir_full}\n# pf_boot.img: {boot.boot_path}\n# Android Platform Tools Version: {get_sdk_version()}\n\n"

    # delete previous flash-pf.bat file if it exists
    if os.path.exists(flash_pf_file):
        os.remove(flash_pf_file)

    #-------------------------------
    # if we are in custom Flash mode
    #-------------------------------
    if self.config.advanced_options and self.config.flash_mode == 'customFlash':
        if self.config.flash_to_inactive_slot:
            fastboot_options += '--slot other '
        if image_mode and get_image_path():
            title = "Advanced Flash Options"
            # create flash-pf.bat based on the custom options.
            f = open(flash_pf_file.strip(), "w", encoding="ISO-8859-1", errors="replace")
            data = first_line
            if sys.platform == "win32":
                data += "PATH=%PATH%;\"%SYSTEMROOT%\System32\"\n"
            # Sideload
            if image_mode == 'SIDELOAD':
                msg  = "\nADB Sideload:           "
                data += f"\"{get_adb()}\" -s {device.id} sideload \"{get_image_path()}\"\n"
            else:
                data += version_sig
                if image_mode == 'image':
                    action = "update"
                    msg  = f"\nFlash {image_mode:<18}"
                elif image_mode == 'boot' and self.live_boot_radio_button.Value:
                    action = "boot"
                    msg  = "\nLive Boot to:           "
                    if device.hardware in ('panther', 'cheetah'):
                        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Live booting Pixel 7 or Pixel 7p is not supported yet.")
                        puml("#orange:Live booting Pixel 7 or Pixel 7p is not supported yet;\n}\n")
                        return
                else:
                    action = f"flash {image_mode}"
                    msg  = f"\nFlash {image_mode:<18}"
                data += f"\"{get_fastboot()}\" -s {device.id} {fastboot_options} {action} \"{get_image_path()}\"\n"

            f.write(data)
            f.close()
            message += f"{msg}{get_image_path()}\n\n"
        else:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: No image file is selected.")
            puml("#red:Image file is not selected;\n}\n")
            return

    #---------------------------
    # do the standard flash mode
    #---------------------------
    else:
        # check for boot file
        if not os.path.exists(boot.boot_path):
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: boot file: {boot.boot_path} is not found.")
            print("Aborting ...\n")
            puml("#red:boot file is not found;\n}\n")
            return
        else:
            # copy boot file to package directory, but first delete an old one to be sure
            pf = os.path.join(package_dir_full, "pf_boot.img")
            if os.path.exists(pf):
                os.remove(pf)
            debug(f"Copying {boot.boot_path} to {pf}")
            shutil.copy(boot.boot_path, pf, follow_symlinks=True)
        if not os.path.exists(pf):
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} boot file: {pf} is not found.")
            print("Aborting ...\n")
            puml("#red:boot file is not found;\n}\n")
            return

        # check for rom file
        if self.config.custom_rom and self.config.advanced_options:
            if not os.path.exists(self.config.custom_rom_path):
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: ROM file: {self.config.custom_rom_path} is not found.")
                print("Aborting ...\n")
                puml("#red:ROM file is not found;\n}\n")
                return
            else:
                # copy ROM file to package directory, but first delete an old one to be sure
                rom_file = ntpath.basename(self.config.custom_rom_path)
                set_custom_rom_file(rom_file)
                rom = os.path.join(package_dir_full, rom_file)
                if os.path.exists(rom):
                    os.remove(rom)
                debug(f"Copying {self.config.custom_rom_path} to {rom}")
                shutil.copy(self.config.custom_rom_path, rom, follow_symlinks=True)
            if not os.path.exists(rom):
                print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ROM file: {rom} is not found.")
                print("Aborting ...\n")
                puml("#red:ROM file is not found;\n}\n")
                return

        # Make sure Phone model matches firmware model
        if get_firmware_model() != device.hardware:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Android device model {device.hardware} does not match firmware Model {get_firmware_model()}")
            puml(f"#orange:Hardware does not match firmware;\n")
            puml(f"note right\nAndroid device model {device.hardware}\nfirmware Model {get_firmware_model()}\nend note\n")
            # return

        # if firmware_model != device.hardware:
            title = "Device / Firmware Mismatch"
            message =  f"ERROR: Your phone model is: {device.hardware}\n\n"
            message += f"The selected firmware is for: {get_firmware_model()}\n\n"
            message += "Unless you know what you are doing, if you continue flashing\n"
            message += "you risk bricking your device, proceed only if you are absolutely\n"
            message += "certian that this is what you want, you have been warned.\n\n"
            message += "Click OK to accept and continue.\n"
            message += "or Hit CANCEL to abort."
            print(f"\n*** Dialog ***\n{message}\n______________\n")
            puml(":Dialog;\n")
            puml(f"note right\n{message}\nend note\n")
            dlg = wx.MessageDialog(None, message, title, wx.CANCEL | wx.OK | wx.ICON_EXCLAMATION)
            result = dlg.ShowModal()
            if result == wx.ID_OK:
                print("User pressed ok.")
                puml(":User Pressed OK;\n")
            else:
                print("User pressed cancel.")
                print("Aborting ...\n")
                puml("#pink:User Pressed Cancel to abort;\n}\n")
                return

        # Process flash_all files
        flash_all_win32 = process_flash_all_file(os.path.join(package_dir_full, "flash-all.bat"))
        if (flash_all_win32 == 'ERROR'):
            print("Aborting ...\n")
            puml("#red:Error processing flash_all.bat file;\n}\n")
            return
        flash_all_linux = process_flash_all_file(os.path.join(package_dir_full, "flash-all.sh"))
        if (flash_all_linux == 'ERROR'):
            print("Aborting ...\n")
            puml("#red:Error processing flash_all.sh file;\n}\n")
            return
        s1 = ''
        s2 = ''
        for f in flash_all_win32:
            if f.sync_line != '':
                s1 += f"{f.sync_line}\n"
        for f in flash_all_linux:
            if f.sync_line != '':
                s2 += f"{f.sync_line}\n"
        # check to see if we have consistent linux / windows files
        if s1 != s2:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Found inconsistency between flash-all.bat and flash-all.sh files.")
            puml("#yellow:Found an inconsistency between bat and sh files;\n")
            debug(f"bat file:\n{s1}")
            debug(f"\nsh file\n{s2}\n")

        if sys.platform == "win32" and cp:
            data = f"chcp {cp}\n"
        else:
            data = ''
        add_echo =''
        if self.config.flash_mode == 'dryRun':
            add_echo = 'echo '

        if sys.platform == "win32":
            flash_all_file = flash_all_win32
        else:
            flash_all_file = flash_all_linux
        for f in flash_all_file:
            if f.type == 'init':
                data += f"{f.full_line}\n"
                if sys.platform == "win32":
                    data += f":: This is a generated file by PixelFlasher v{VERSION}\n"
                    data += f":: cd {package_dir_full}\n"
                    data += f":: pf_boot.img: {boot.boot_path}\n"
                    data += f":: Android Platform Tools Version: {get_sdk_version()}\n\n"
                else:
                    data += f"# This is a generated file by PixelFlasher v{VERSION}\n"
                    data += f"# cd {package_dir_full}\n"
                    data += f"# pf_boot.img: {boot.boot_path}\n"
                    data += f"# Android Platform Tools Version: {get_sdk_version()}\n\n"
                if self.config.flash_to_inactive_slot:
                    data += "echo Switching active slot to the other ...\n"
                    data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} --set-active=other\n"
                continue
            if f.type in ['sleep']:
                sleep_line = f"{f.full_line}\n"
                data += f"{f.full_line}\n"
                continue
            if f.type in ['path']:
                data += f"{f.full_line}\n"
                continue
            if f.action == 'reboot-bootloader':
                data += f"\"{get_fastboot()}\" -s {device.id} {f.action} {f.arg1} {f.arg2}\n"
                continue
            if f.action == 'flash':
                data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options} {f.action} {f.arg1} {f.arg2}\n"
                continue
            if f.action == '-w update':
                action = '--skip-reboot update'
                arg1 = f.arg1
                if self.config.flash_mode == 'wipeData':
                    action = '--skip-reboot -w update'
                if self.config.custom_rom and self.config.advanced_options:
                    arg1 = f"\"{get_custom_rom_file()}\""
                data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options2} {action} {arg1}\n"
                # flash on each slot separately
                # https://forum.xda-developers.com/t/psa-do-not-try-to-boot-into-the-old-slot-after-updating-only-one-slot-to-android-13-unlocking-the-pixel-6-pro-bootloader-central-repository.4352027/post-87309913
                if self.config.advanced_options and self.config.flash_both_slots:
                    data += "echo Switching active slot to the other ...\n"
                    data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} --set-active=other\n"
                    data += "echo rebooting to bootloader ...\n"
                    data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} reboot bootloader\n"
                    data += "echo Sleeping 5-10 seconds ...\n"
                    data += sleep_line
                    data += sleep_line
                    data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options2} {action} {arg1}\n"
        # add the boot.img flashing
        data += "echo rebooting to bootloader ...\n"
        data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} reboot bootloader\n"
        data += "echo Sleeping 5-10 seconds ...\n"
        data += sleep_line
        data += sleep_line
        if self.config.temporary_root and boot.is_patched:
            data += "echo Live booting to pf_boot (temporary root) ...\n"
            data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options} boot pf_boot.img\n"
        else:
            data += "echo flashing pf_boot ...\n"
            if 'panther' in get_firmware_model() or 'cheetah' in get_firmware_model():
                data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options} flash init_boot pf_boot.img\n"
            else:
                data += f"{add_echo}\"{get_fastboot()}\" -s {device.id} {fastboot_options} flash boot pf_boot.img\n"
            # only reboot if no_reboot is not selected.
            if not self.config.no_reboot:
                data += "echo rebooting to system ...\n"
                data += f"\"{get_fastboot()}\" -s {device.id} reboot"

        fin = open(flash_pf_file, "wt", encoding="ISO-8859-1", errors="replace")
        fin.write(data)
        fin.close()

        title = "Flash Options"
        message = get_flash_settings(self) + message + '\n'

    #----------------------------------------
    # common part for package or custom flash
    #----------------------------------------
    # make the sh script executable
    if sys.platform != "win32":
        theCmd = f"chmod 755 \"{flash_pf_file}\""
        debug(theCmd)
        res = run_shell(theCmd)
        if res.returncode != 0:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Could not set the permissions on {flash_pf_file}")
            print(f"Return Code: {res.returncode}.")
            print(f"Stdout: {res.stdout}.")
            print(f"Stderr: {res.stderr}.")
            print("Aborting ...\n")
            puml("#red:Could not set the permissions on flash script;\n}\n")
            return

    message += "\nNote: Pressing OK button will invoke a script that will utilize\n"
    if self.config.advanced_options and self.config.flash_mode == 'customFlash' and image_mode == 'SIDELOAD':
        message += "adb command, this could possibly take a long time and PixelFlasher\n"
        message += "will appear frozen. PLEASE BE PATIENT and don\'t interrupt the process.\n\n"
    else:
        message += "fastboot commands, this could possibly take a long time and PixelFlasher\n"
        message += "will appear frozen. PLEASE BE PATIENT. \n"
        message += "In case it takes excessively long, it could possibly be due to improper or\n"
        message += "bad fasboot drivers.\n"
        message += "In such cases, killing the fastboot process will resume to normalcy.\n\n"
    message += "Do you want to continue to flash with the above options?\n"
    message += "You can also choose to edit the script before continuing,\nin case you want to customize it.(Only choose this if you know what you are doing)\n\n"
    message += "Press OK to continue or CANCEL to abort.\n"
    print(f"\n*** Dialog ***\n{message}\n______________\n")
    print(f"The script content that will be executed:")
    print(f"___________________________________________________\n{data}")
    print("___________________________________________________\n")
    puml(":Dialog;\n", True)
    puml(f"note right\n{message}end note\n")
    puml(":Script;\n")
    puml(f"note right\nFlash Script\n====\n{data}\nend note\n")
    set_message_box_title(title)
    set_message_box_message(message)
    dlg = MessageBoxEx(parent=None, button_texts=["OK", "Edit script before continuing", "Cancel"], default_button=1)
    dlg.CentreOnParent(wx.BOTH)
    result = dlg.ShowModal()
    dlg.Destroy()
    if result == 1: # OK
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Ok.")
        puml(":User Pressed OK;\n")
        # continue flashing
    elif result == 2: # Edit
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Edit Script.")
        puml("#pink:User Pressed Edit Script;\n}\n")
        dlg = FileEditor(self, flash_pf_file)
        dlg.CenterOnParent()
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_OK:
            # get the contents of modified flash_pf_file
            with open(flash_pf_file, 'r') as f:
                contents = f.read()
            print(f"\nflash_pf file has been modified!")
            print(f"The modified script content that will be executed:")
            print(f"___________________________________________________\n{contents}")
            print("___________________________________________________\n")
            puml(f"note right\nModified Script\n====\n{contents}\nend note\n")
            # continue flashing
        else:
            print("User cancelled editing flash_phone file.")
            puml(f"note right\nCancelled and Aborted\nend note\n")
            return
    elif result == 3: # Cancel
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User Pressed Cancel.")
        print("Aborting ...\n")
        puml("#pink:User Pressed Cancel;\n}\n")
        return

    print("")
    print("==============================================================================")
    print(f" {datetime.now():%Y-%m-%d %H:%M:%S} PixelFlasher {VERSION}              Flashing Phone    ")
    print("==============================================================================")
    startFlash = time.time()
    puml(":Start Flashing;\n", True)
    print(f"Android Platform Tools Version: {get_sdk_version()}")
    puml(f"note right\nPixelFlasher {VERSION}\nAndroid Platform Tools Version: {get_sdk_version()}\nend note\n")

    # If we're doing Sideload flashing
    if self.config.advanced_options and self.config.flash_mode == 'customFlash' and image_mode == 'SIDELOAD':
        device.reboot_sideload()
        print("Waiting 20 seconds ...")
        time.sleep(20)
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Flashing device {device.id} ...")
        puml(f":Flashing device {device.id};\n", True)
        theCmd = flash_pf_file
        os.chdir(package_dir_full)
        debug(f"Running in Directory: {package_dir_full}")
        theCmd = f"\"{theCmd}\""
        debug(theCmd)
        run_shell2(theCmd)
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Done!")
        endFlash = time.time()
        print(f"Flashing elapsed time: {math.ceil(endFlash - startFlash)} seconds")
        print("------------------------------------------------------------------------------\n")
        os.chdir(cwd)
        puml("#cee7ee:End Flashing;\n", True)
        puml(f"note right:Flash time: {math.ceil(endFlash - startFlash)} seconds;\n")
        puml("}\n")
        return

    if device.mode == 'adb':
        device.reboot_bootloader()
        print("Waiting 10 seconds ...")
        time.sleep(10)
        # device.refresh_phone_mode()
        self.device_choice.SetItems(get_connected_devices())
        self._select_configured_device()

    device = get_phone()
    if not device:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to detect the device.")
        puml("#red:Valid device is not detected;\n}\n")
        # let's try one more time just in case
        print("Waiting 10 seconds ...")
        time.sleep(10)
        self.device_choice.SetItems(get_connected_devices())
        self._select_configured_device()
        device = get_phone()
        if not device:
            print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Unable to detect the device.")
            puml("#red:Valid device is not detected;\n}\n")
        return

    if not (device.unlocked or (self.config.advanced_options and self.config.flash_mode == 'customFlash' and image_mode == 'SIDELOAD')):
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Bootloader is locked, can't flash.")
        print("Aborting ...\n")
        puml("#red:Bootloader is locked, can't flash;\n}\n")
        return

    # some images need to be flashed in fastbootd mode
    # note: system and vendor, typically get flashed to both slots. '--skip-secondary' will not flash secondary slots in flashall/update
    # TODO check which Pixels and newer support fastbootd, Probably Pixel 5 and newer.
    if self.config.advanced_options and self.config.flash_mode == 'customFlash' and get_image_mode() in ['super','product','system','system_dlkm','system_ext','vendor','vendor_dlkm']:
        device.reboot_fastboot()
        print("Waiting 5 seconds ...")
        time.sleep(5)

    # if in bootloader mode, Start flashing
    if device.mode == 'f.b' and get_fastboot():
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Flashing device {device.id} ...")
        puml(f":Flashing device {device.id};\n", True)
        # confirm for wipe data
        if self.config.flash_mode == 'wipeData':
            print("Flash Mode: Wipe Data")
            puml(f":Flash Mode: Wipe Data;\n")
            dlg = wx.MessageDialog(None, "You have selected to WIPE data\nAre you sure want to continue?",'Wipe Data',wx.YES_NO | wx.ICON_EXCLAMATION)
            puml(f"note right\nDialog\n====\nYou have selected to WIPE data\nAre you sure want to continue?\nend note\n")
            result = dlg.ShowModal()
            if result != wx.ID_YES:
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User canceled flashing.")
                puml("#pink:User cancelled flashing;\n}\n")
                return
        # confirm for force flag
        if self.config.advanced_options and self.config.fastboot_force:
            print("Flash Option: Force")
            dlg = wx.MessageDialog(None, "You have selected to flash option: Force\nThis will wipe your data\nAre you sure want to continue?",'Flash option: Force',wx.YES_NO | wx.ICON_EXCLAMATION)
            puml(f"note right\nDialog\n====\nYou have selected to flash option: Force\nThis will wipe your data\nAre you sure want to continue?\nend note\n")
            result = dlg.ShowModal()
            if result != wx.ID_YES:
                print(f"{datetime.now():%Y-%m-%d %H:%M:%S} User canceled flashing.")
                puml("#pink:User cancelled flashing;\n}\n")
                return

        theCmd = flash_pf_file
        os.chdir(package_dir_full)
        theCmd = f"\"{theCmd}\""
        debug(theCmd)
        run_shell2(theCmd)
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Done!")
        endFlash = time.time()
        print(f"Flashing elapsed time: {math.ceil(endFlash - startFlash)} seconds")
        print("------------------------------------------------------------------------------\n")
        puml("#cee7ee:End Flashing;\n", True)
        puml(f"note right:Flash time: {math.ceil(endFlash - startFlash)} seconds;\n")
        puml("}\n")
        os.chdir(cwd)
        # clear the selected device option
        set_phone(None)
        self.device_label.Label = "ADB Connected Devices"
        self.config.device = None
        self.device_choice.SetItems([''])
        self.device_choice.Select(0)
        if self.config.advanced_options and self.config.flash_mode == 'customFlash':
            print("\nNote: The device is intentionally kept in bootloader mode\nin case you want to flash or do more things before booting to system.\nYou can reboot to system by pressing the button in PixelFlasher, or on your phone.\n")
    else:
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: Device {device.id} not in bootloader mode.")
        print(f"{datetime.now():%Y-%m-%d %H:%M:%S} Aborting ...\n")
        puml("#red:Device is not in bootloader mode;\n}\n")

