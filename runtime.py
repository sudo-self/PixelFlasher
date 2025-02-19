#!/usr/bin/env python

import os
import sqlite3 as sl
import sys
from datetime import datetime

import requests
from packaging.version import parse
from platformdirs import *

from config import VERSION

APPNAME = 'PixelFlasher'
CONFIG_FILE_NAME = 'PixelFlasher.json'

verbose = False
adb = None
fastboot = None
phones = []
phone = None
advanced_options = False
update_check = True
firmware_model = None
firmware_id = None
custom_rom_id = None
logfile = None
pumlfile = None
sdk_version = None
image_mode = None
image_path = None
custom_rom_file = None
message_box_title = None
message_box_message = None
version = None
db = None
boot = None
system_code_page = None
codepage_setting = False
codepage_value = ''
magisk_package = ''
patched_with = ''
customize_font = False
pf_font_face = ''
pf_font_size = 12
app_labels = {}
lineage = False
a_only = False

# ============================================================================
#                               Class Boot
# ============================================================================
class Boot():
    def __init__(self):
        self.boot_id = None
        self.boot_hash = None
        self.boot_path = None
        self.is_patched = None
        self.magisk_version = None
        self.hardware = None
        self.boot_epoch = None
        self.package_id = None
        self.package_boot_hash = None
        self.package_type = None
        self.package_sig = None
        self.get_package_path = None
        self.package_epoch = None


# ============================================================================
#                               Function get_boot
# ============================================================================
def get_boot():
    global boot
    return boot


# ============================================================================
#                               Function set_boot
# ============================================================================
def set_boot(value):
    global boot
    boot = value


# ============================================================================
#                               Function get_labels
# ============================================================================
def get_labels():
    global app_labels
    return app_labels


# ============================================================================
#                               Function set_labels
# ============================================================================
def set_labels(value):
    global app_labels
    app_labels = value


# ============================================================================
#                               Function get_patched_with
# ============================================================================
def get_patched_with():
    global patched_with
    return patched_with


# ============================================================================
#                               Function set_patched_with
# ============================================================================
def set_patched_with(value):
    global patched_with
    patched_with = value


# ============================================================================
#                               Function get_db
# ============================================================================
def get_db():
    global db
    return db


# ============================================================================
#                               Function set_db
# ============================================================================
def set_db(value):
    global db
    db = value


# ============================================================================
#                               Function get_boot_images_dir
# ============================================================================
def get_boot_images_dir():
    # boot_images did not change at version 5, so we can keep on using 4
    if parse(VERSION) < parse('4.0.0'):
        return 'boot_images'
    else:
        return 'boot_images4'


# ============================================================================
#                               Function get_factory_images_dir
# ============================================================================
def get_factory_images_dir():
    # factory_images only changed after version 5
    if parse(VERSION) < parse('5.0.0'):
        return 'factory_images'
    else:
        return 'factory_images5'


# ============================================================================
#                               Function get_pf_db
# ============================================================================
def get_pf_db():
    # we have different db schemas for each of these versions
    if parse(VERSION) < parse('4.0.0'):
        return 'PixelFlasher.db'
    elif parse(VERSION) < parse('5.0.0'):
        return 'PixelFlasher4.db'
    else:
        return 'PixelFlasher5.db'


# ============================================================================
#                               Function get_verbose
# ============================================================================
def get_verbose():
    global verbose
    return verbose


# ============================================================================
#                               Function set_verbose
# ============================================================================
def set_verbose(value):
    global verbose
    verbose = value


# ============================================================================
#                               Function get_lineage
# ============================================================================
def get_lineage():
    global lineage
    return lineage


# ============================================================================
#                               Function set_lineage
# ============================================================================
def set_lineage(value):
    global lineage
    lineage = value


# ============================================================================
#                               Function get_a_only
# ============================================================================
def get_a_only():
    global a_only
    return a_only


# ============================================================================
#                               Function set_a_only
# ============================================================================
def set_a_only(value):
    global a_only
    a_only = value


# ============================================================================
#                               Function get_adb
# ============================================================================
def get_adb():
    global adb
    return adb


# ============================================================================
#                               Function set_adb
# ============================================================================
def set_adb(value):
    global adb
    adb = value


# ============================================================================
#                               Function get_fastboot
# ============================================================================
def get_fastboot():
    global fastboot
    return fastboot


# ============================================================================
#                               Function set_fastboot
# ============================================================================
def set_fastboot(value):
    global fastboot
    fastboot = value


# ============================================================================
#                               Function get_phones
# ============================================================================
def get_phones():
    global phones
    return phones


# ============================================================================
#                               Function set_phones
# ============================================================================
def set_phones(value):
    global phones
    phones = value


# ============================================================================
#                               Function get_phone
# ============================================================================
def get_phone():
    global phone
    return phone


# ============================================================================
#                               Function set_phone
# ============================================================================
def set_phone(value):
    global phone
    phone = value


# ============================================================================
#                               Function get_system_codepage
# ============================================================================
def get_system_codepage():
    global system_code_page
    return system_code_page


# ============================================================================
#                               Function set_system_codepage
# ============================================================================
def set_system_codepage(value):
    global system_code_page
    system_code_page = value


# ============================================================================
#                               Function get_codepage_setting
# ============================================================================
def get_codepage_setting():
    global codepage_setting
    return codepage_setting


# ============================================================================
#                               Function set_codepage_setting
# ============================================================================
def set_codepage_setting(value):
    global codepage_setting
    codepage_setting = value


# ============================================================================
#                               Function get_codepage_value
# ============================================================================
def get_codepage_value():
    global codepage_value
    return codepage_value


# ============================================================================
#                               Function set_codepage_value
# ============================================================================
def set_codepage_value(value):
    global codepage_value
    codepage_value = value


# ============================================================================
#                               Function get_pf_font_face
# ============================================================================
def get_pf_font_face():
    global pf_font_face
    return pf_font_face


# ============================================================================
#                               Function set_pf_font_face
# ============================================================================
def set_pf_font_face(value):
    global pf_font_face
    pf_font_face = value


# ============================================================================
#                               Function get_pf_font_size
# ============================================================================
def get_pf_font_size():
    global pf_font_size
    return pf_font_size


# ============================================================================
#                               Function set_pf_font_size
# ============================================================================
def set_pf_font_size(value):
    global pf_font_size
    pf_font_size = value


# ============================================================================
#                               Function get_customize_font
# ============================================================================
def get_customize_font():
    global customize_font
    return customize_font


# ============================================================================
#                               Function set_customize_font
# ============================================================================
def set_customize_font(value):
    global customize_font
    customize_font = value


# ============================================================================
#                               Function get_magisk_package
# ============================================================================
def get_magisk_package():
    global magisk_package
    return magisk_package


# ============================================================================
#                               Function set_magisk_package
# ============================================================================
def set_magisk_package(value):
    global magisk_package
    magisk_package = value


# ============================================================================
#                               Function get_advanced_options
# ============================================================================
def get_advanced_options():
    global advanced_options
    return advanced_options


# ============================================================================
#                               Function set_advanced_options
# ============================================================================
def set_advanced_options(value):
    global advanced_options
    advanced_options = value


# ============================================================================
#                               Function get_update_check
# ============================================================================
def get_update_check():
    global update_check
    return update_check


# ============================================================================
#                               Function set_update_check
# ============================================================================
def set_update_check(value):
    global update_check
    update_check = value


# ============================================================================
#                               Function get_firmware_model
# ============================================================================
def get_firmware_model():
    global firmware_model
    return firmware_model


# ============================================================================
#                               Function set_firmware_model
# ============================================================================
def set_firmware_model(value):
    global firmware_model
    firmware_model = value


# ============================================================================
#                               Function get_firmware_id
# ============================================================================
def get_firmware_id():
    global firmware_id
    return firmware_id


# ============================================================================
#                               Function set_firmware_id
# ============================================================================
def set_firmware_id(value):
    global firmware_id
    firmware_id = value


# ============================================================================
#                               Function get_custom_rom_id
# ============================================================================
def get_custom_rom_id():
    global custom_rom_id
    return custom_rom_id


# ============================================================================
#                               Function set_custom_rom_id
# ============================================================================
def set_custom_rom_id(value):
    global custom_rom_id
    custom_rom_id = value


# ============================================================================
#                               Function get_logfile
# ============================================================================
def get_logfile():
    global logfile
    return logfile


# ============================================================================
#                               Function set_logfile
# ============================================================================
def set_logfile(value):
    global logfile
    logfile = value


# ============================================================================
#                               Function get_pumlfile
# ============================================================================
def get_pumlfile():
    global pumlfile
    return pumlfile


# ============================================================================
#                               Function set_pumlfile
# ============================================================================
def set_pumlfile(value):
    global pumlfile
    pumlfile = value


# ============================================================================
#                               Function get_sdk_version
# ============================================================================
def get_sdk_version():
    global sdk_version
    return sdk_version


# ============================================================================
#                               Function set_sdk_version
# ============================================================================
def set_sdk_version(value):
    global sdk_version
    sdk_version = value


# ============================================================================
#                               Function get_image_mode
# ============================================================================
def get_image_mode():
    global image_mode
    return image_mode


# ============================================================================
#                               Function set_image_mode
# ============================================================================
def set_image_mode(value):
    global image_mode
    image_mode = value


# ============================================================================
#                               Function get_image_path
# ============================================================================
def get_image_path():
    global image_path
    return image_path


# ============================================================================
#                               Function set_image_path
# ============================================================================
def set_image_path(value):
    global image_path
    image_path = value


# ============================================================================
#                               Function get_custom_rom_file
# ============================================================================
def get_custom_rom_file():
    global custom_rom_file
    return custom_rom_file


# ============================================================================
#                               Function set_custom_rom_file
# ============================================================================
def set_custom_rom_file(value):
    global custom_rom_file
    custom_rom_file = value


# ============================================================================
#                               Function get_message_box_title
# ============================================================================
def get_message_box_title():
    global message_box_title
    return message_box_title


# ============================================================================
#                               Function set_message_box_title
# ============================================================================
def set_message_box_title(value):
    global message_box_title
    message_box_title = value


# ============================================================================
#                               Function get_message_box_message
# ============================================================================
def get_message_box_message():
    global message_box_message
    return message_box_message


# ============================================================================
#                               Function set_message_box_message
# ============================================================================
def set_message_box_message(value):
    global message_box_message
    message_box_message = value


# ============================================================================
#                               Function get_config_path
# ============================================================================
def get_config_path():
    return user_data_dir(APPNAME, appauthor=False, roaming=True)


# ============================================================================
#                               Function puml
# ============================================================================
def puml(message='', left_ts = False, mode='a'):
    with open(get_pumlfile(), mode, encoding="ISO-8859-1", errors="replace") as puml_file:
        puml_file.write(message)
        if left_ts:
            puml_file.write(f"note left:{datetime.now():%Y-%m-%d %H:%M:%S}\n")


# ============================================================================
#                               Function init_config_path
# ============================================================================
def init_config_path():
    config_path = get_config_path()
    if not os.path.exists(os.path.join(config_path, 'logs')):
        os.makedirs(os.path.join(config_path, 'logs'), exist_ok=True)
    if not os.path.exists(os.path.join(config_path, 'factory_images')):
        os.makedirs(os.path.join(config_path, 'factory_images'), exist_ok=True)
    if not os.path.exists(os.path.join(config_path, get_boot_images_dir())):
        os.makedirs(os.path.join(config_path, get_boot_images_dir()), exist_ok=True)
    if not os.path.exists(os.path.join(config_path, 'tmp')):
        os.makedirs(os.path.join(config_path, 'tmp'), exist_ok=True)
    if not os.path.exists(os.path.join(config_path, 'puml')):
        os.makedirs(os.path.join(config_path, 'puml'), exist_ok=True)


# ============================================================================
#                               Function init_db
# ============================================================================
def init_db():
    global db
    config_path = get_config_path()
    # connect / create db
    db = sl.connect(os.path.join(config_path, get_pf_db()))
    db.execute("PRAGMA foreign_keys = ON")
    # create tables
    with db:
        # there could be more than one package that has the same boot.img
        # PACKAGE Table
        db.execute("""
            CREATE TABLE IF NOT EXISTS PACKAGE (
                id INTEGER NOT NULL PRIMARY KEY,
                boot_hash TEXT NOT NULL,
                type TEXT CHECK (type IN ('firmware', 'rom')) NOT NULL,
                package_sig TEXT NOT NULL,
                file_path TEXT NOT NULL UNIQUE,
                epoch INTEGER NOT NULL
            );
        """)
        # BOOT Table
        db.execute("""
            CREATE TABLE IF NOT EXISTS BOOT (
                id INTEGER NOT NULL PRIMARY KEY,
                boot_hash TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL,
                is_patched INTEGER CHECK (is_patched IN (0, 1)),
                magisk_version TEXT,
                hardware TEXT,
                epoch INTEGER NOT NULL
            );
        """)
        # PACKAGE_BOOT Table
        db.execute("""
            CREATE TABLE IF NOT EXISTS PACKAGE_BOOT (
                package_id INTEGER,
                boot_id INTEGER,
                epoch INTEGER NOT NULL,
                PRIMARY KEY (package_id, boot_id),
                FOREIGN KEY (package_id) REFERENCES PACKAGE(id),
                FOREIGN KEY (boot_id) REFERENCES BOOT(id)
            );
        """)


# ============================================================================
#                               Function get_config_file_path
# ============================================================================
def get_config_file_path():
    return os.path.join(get_config_path(), CONFIG_FILE_NAME).strip()


# ============================================================================
#                               Function get_labels_file_path
# ============================================================================
def get_labels_file_path():
    return os.path.join(get_config_path(), "labels.json").strip()


# ============================================================================
#                               Function get_path_to_7z
# ============================================================================
def get_path_to_7z():
    if sys.platform == "win32":
        path_to_7z =  os.path.join(get_bundle_dir(),'bin', '7z.exe')
    elif sys.platform == "darwin":
        path_to_7z =  os.path.join(get_bundle_dir(),'bin', '7zz')
    else:
        path_to_7z =  os.path.join(get_bundle_dir(),'bin', '7zzs')

    if not os.path.exists(path_to_7z):
        print(f"\n{datetime.now():%Y-%m-%d %H:%M:%S} ERROR: {path_to_7z} is not found")
        return None
    return path_to_7z


# ============================================================================
#                               Function get_bundle_dir
# ============================================================================
# set by PyInstaller, see http://pyinstaller.readthedocs.io/en/v3.2/runtime-information.html
# https://stackoverflow.com/questions/7674790/bundling-data-files-with-pyinstaller-onefile
def get_bundle_dir():
    if getattr(sys, 'frozen', False):
        # noinspection PyUnresolvedReferences,PyProtectedMember
        # running in a bundle
        return sys._MEIPASS
    else:
        # running live
        return os.path.dirname(os.path.abspath(__file__))


# ============================================================================
#                               Function check_latest_version
# ============================================================================
def check_latest_version():
    try:
        response = requests.get('https://github.com/badabing2005/PixelFlasher/releases/latest')
        # look in history to find the 302, and get the loaction header
        location = response.history[0].headers['Location']
        # split by '/' and get the last item
        l_version = location.split('/')[-1]
        # If it starts with v, remove it
        if l_version[:1] == "v":
            version = l_version[1:]
        if version.count('.') == 2:
            version = f"{version}.0"
    except Exception:
        version = '0.0.0.0'
    return version


# ============================================================================
#                               Function grow_column
# ============================================================================
def grow_column(list, col, value = 20):
    w = list.GetColumnWidth(col)
    list.SetColumnWidth(col, w + value)
