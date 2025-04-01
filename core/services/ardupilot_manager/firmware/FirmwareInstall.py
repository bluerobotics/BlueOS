import json
import os
import pathlib
import platform as system_platform
import shutil
import stat
from typing import Optional, Union

from ardupilot_fw_decoder import BoardSubType, BoardType, Decoder
from elftools.elf.elffile import ELFFile
from loguru import logger

from exceptions import FirmwareInstallFail, InvalidFirmwareFile, UnsupportedPlatform
from firmware.FirmwareDownload import FirmwareDownloader
from firmware.FirmwareUpload import FirmwareUploader
from typedefs import FirmwareFormat, FlightController, Platform, PlatformType


def get_board_id(board: Union[FlightController, str]) -> int:
    print(board)
    if isinstance(board, FlightController):
        platform = board.name
    else:
        platform = board
    ardupilot_board_ids = {
        Platform.Pixhawk1: 9,
        Platform.Pixhawk4: 50,
        Platform.Pixhawk6X: 53,
        Platform.Pixhawk6C: 56,
        Platform.CubeOrange: 140,
        "PX4_FMU_V1": 5,
        "PX4_FMU_V2": 9,
        "PX4_FMU_V3": 9,  # same as FMU_V2
        "PX4_FMU_V4": 11,
        "PX4_FMU_V4_PRO": 13,
        "UVIFY_CORE": 20,
        "PX4_FMU_V5": 50,
        "PX4_FMU_V5X": 51,
        "PX4_FMU_V6": 52,
        "PX4_FMU_V6X": 53,
        "ARK_FMU_V6X": 57,
        "MINDPX_V2": 88,
        "PX4_FLOW_V1": 6,
        "PX4_DISCOVERY_V1": 99,
        "PX4_PIO_V1": 10,
        "PX4_PIO_V2": 10,  # same as PIO_V1
        "PX4_PIO_V3": 13,
        "PX4_AEROCORE_V1": 98,
        "TAP_V1": 64,
        "CRAZYFLIE": 12,
        "CRAZYFLIE21": 14,
        "OMNIBUSF4SD": 42,
        "AUAV_X2V1": 33,
        "AEROFC_V1": 65,
        "TARGET_TAP_V2": 66,
        "CUBE_F4": 9,
        "AV_V1": 29,
        "KAKUTEF7": 123,
        "SMARTAP_AIRLINK": 55,
        "SMARTAP_PRO": 32,
        "MODALAI_FC_V1": 41775,
        "MODALAI_FC_V2": 41776,
        "MODALAI_VOXL2_IO": 41777,
        "HOLYBRO_PIX32_V5": 78,
        "HOLYBRO_CAN_GPS": 79,
        "FMUK66_V3": 28,
        "AV_X_V1": 29,
        "FMUK66_E": 30,
        "FMURT1062-V1": 31,
        "ARK_CAN_FLOW": 80,
        "ARK_CAN_GPS": 81,
        "ARK_CAN_RTK_GPS": 82,
        "ARK_CANNODE": 83,
        "FF_RTK_CAN_GPS": 85,
        "PDW_MAS_MAIN-V1": 86,
        "ATL_MANTIS_EDU": 97,
        "THE_PEACH_K1": 212,
        "THE_PEACH_R1": 213,
        "CUBEYELLOW": 120,
        "OMNIBUSF7V2": 121,
        "KAKUTEF4": 122,
        "REVOLUTION": 124,
        "MATEKF405": 125,
        "NUCLEOF767ZI": 126,
        "MATEKF405_WING": 127,
        "AIRBOTF4": 128,
        "SPARKYV2": 130,
        "OMNIBUSF4PRO": 131,
        "ANYFCF7": 132,
        "OMNIBUSNANOV6": 133,
        "SPEEDYBEEF4": 134,
        "F35LIGHTNING": 135,
        "MRO_X2V1_777": 136,
        "OMNIBUSF4V6": 137,
        "HELIOSPRING": 138,
        "DURANDAL": 139,
        "CUBEORANGE": 140,
        "MRO_CONTROL_ZERO": 141,
        "MRO_CONTROL_ZERO_OEM": 142,
        "MATEKF765_WING": 143,
        "JDMINIF405": 144,
        "KAKUTEF7_MINI": 145,
        "H757I_EVAL": 146,
        "F4BY": 20,  # value due to previous release by vendor
        "MAZZYSTARDRONE": 188,
        "VRBRAIN_V51": 1151,
        "VRBRAIN_V52": 1152,
        "VRBRAIN_V54": 1154,
        "VRCORE_V10": 1910,
        "VRUBRAIN_V51": 1351,
        "F103_PERIPH": 1000,
        "CUAV_GPS": 1001,
        "OMNIBUSF4": 1002,
        "CUBEBLACKPLUS": 1003,
        "F303_PERIPH": 1004,
        "ZUBAXGNSS": 1005,
        "NIGHTCRAWLER": 1006,
        "SKYBOT": 1007,
        "FRSKY_R9": 1008,
        "CUAV_NORA": 1009,
        "CUAV_X7_PRO": 1010,
        "SUCCEXF4": 1011,
        "LIGHTSPARKMINI": 1012,
        "MATEKH743": 1013,
        "MATEKF405_GPS": 1014,
        "MRO_NEXUS": 1015,
        "HITEC_MOSAIC": 1016,
        "MRO_PIXRACER_PRO": 1017,
        "TWD_H7": 1018,
        "MAMBA405": 1019,
        "H31_PIXC4": 1020,
        "QioTekZealotF427": 1021,
        "MRO_CTRL_ZERO_CLASSIC": 1022,
        "MRO_CTRL_ZERO_H7": 1023,
        "MRO_CTRL_ZERO_OEM_H7": 1024,
        "BEASTH7": 1025,
        "BEASTF7": 1026,
        "FlywooF745": 1027,
        "FreeflyRTK": 1028,
        "luminousbee5": 1029,
        "KAKUTEF4_MINI": 1030,
        "H31_PIXC4_PI": 1031,
        "H31_PIXC4_JETSON": 1032,
        "CUBEORANGE_JOEY": 1033,
        "SierraF9P": 1034,
        "HolybroGPS": 1035,
        "QioTekZealotH743": 1036,
        "HEREPRO": 1037,
        "MAMBABASICF4": 1038,
        "ARGOSDYNE_DP1000": 1039,
        "Nucleo491": 1040,
        "mRoM10095": 1041,
        "FlywooF745Nano": 1042,
        "HERE3PLUS": 1043,
        "BirdCANdy": 1044,
        "SKYSTARSF405DJI": 1045,
        "HITEC_AIRSPEED": 1046,
        "NucleoL496": 1047,
        "KakuteH7": 1048,
        "ICSI_Kestrel": 1049,
        "SierraL431": 1050,
        "NucleoL476": 1051,
        "SierraF405": 1052,
        "CarbonixL496": 1053,
        "MatekF405_TE": 1054,
        "SierraF412": 1055,
        "BEASTH7v2": 1056,
        "BEASTF7v2": 1057,
        "KakuteH7Mini": 1058,
        "JHEMCUGSF405A": 1059,
        "SPRACINGH7": 1060,
        "DEVEBOXH7": 1061,
        "MatekL431": 1062,
        "CUBEORANGEPLUS": 1063,
        "CarbonixF405": 1064,
        "QioTekAdeptF407": 1065,
        "QioTekAdeptF427": 1066,
        "FlyingMoonF407": 1067,
        "FlyingMoonF427": 1068,
        "CUBERED_PRIMARY": 1069,
        "CUBERED_SECONDARY": 1070,
        "GreenSight_UltraBlue": 1071,
        "GreenSight_microBlue": 1072,
        "MAMBAH743_V4": 1073,
        "REAPERF745_V2": 1074,
        "SKYSTARSH7HD": 1075,
        "PixSurveyA1": 1076,
        "AEROFOX_AIRSPEED": 1077,
        "ATOMRCF405": 1078,
        "CUBENODE": 1079,
        "AEROFOX_PMU": 1080,
        "JHEMCUGF16F405": 1081,
        "SPEEDYBEEF4V3": 1082,
        "PixPilot-V6": 1083,
        "JFB100": 1084,
        "C_RTK2_HP": 1085,
        "JUMPER_XIAKE800": 1086,
        "Sierra_F1": 1087,
        "HolybroCompass": 1088,
        "FOXEERH743_V1": 1089,
        "PixFlamingoL4R5_V1": 1090,
        "Sierra-TrueNavPro": 1091,
        "Sierra-TrueNav": 1092,
        "Sierra-TrueNorth": 1093,
        "Sierra-TrueSpeed": 1094,
        "Sierra-PrecisionPoint": 1095,
        "PixPilot-V3": 1096,
        "PixSurveyA2": 1097,
        "mRoCANPWM": 1098,
        "FlywooF405S_AIO": 1099,
        "mRoCANPower": 1100,
        "mRoControlOne": 1101,
        "rFCU": 1102,
        "rGNSS": 1103,
        "AEROFOX_AIRSPEED_DLVR": 1104,
        "KakuteH7-Wing": 1105,
        "SpeedyBeeF405WING": 1106,
        "PixSurveyA-IND": 1107,
        "SPRACINGH7RF": 1108,
        "AEROFOX_GNSS_F9P": 1109,
        "JFB110": 1110,
        "SDMODELH7V1": 1111,
        "FlyingMoonH743": 1112,
        "YJUAV_A6": 1113,
        "YJUAV_A6Nano": 1114,
        "ACNS_CM4PILOT": 1115,
        "ACNS_F405AIO": 1116,
        "BLITZF7AIO": 1117,
        "RADIX2HD": 1118,
        "HEEWING_F405": 1119,
        "PodmanH7": 1120,
        "mRo-M10053": 1121,
        "mRo-M10044": 1122,
        "SIYI_N7": 1123,
        "mRoCZOEM_revG": 1124,
        "BETAFPV_F405": 1125,
        "QioTekAdeptH743": 1126,
        "YJUAV_A6SE": 1127,
        "QioTekAdept_6C": 1128,
        "PixFlamingoL4R5_V2": 1129,
        "PixFlamingoF427_V1": 1130,
        "PixFlamingoF767_V1": 1131,
        "PixFlamingoH743I": 1132,
        "PixFlamingoH743V": 1133,
        "AR-F407SmartBat": 1134,
        "SPEEDYBEEF4MINI": 1135,
        "SPEEDYBEEF4V4": 1136,
        "FlywooF405Pro": 1137,
        "TMOTORH7": 1138,
        "MICOAIR405": 1139,
        "PixPilot-C3": 1140,
        "YJUAV_A6SE_H743": 1141,
        "FSO_POWER_STACK": 1142,
        "ATOMRCF405NAVI_DLX": 1143,
        "YJUAV_A6Ultra": 1144,
        "TULIP_BATTMON": 1145,
        "AnyleafH7": 1146,
        "mRoKitCANrevC": 1147,
        "BotBloxSwitch": 1148,
        "MatekH7A3": 1149,
        "MicoAir405v2": 1150,
        "ORAQF405PRO": 1155,
        "CBU_StampH743": 1156,
        "FOXEERF405_V2": 1157,
        "CSKY405": 1158,
        "NxtPX4v2": 1159,
        "PixPilot-V6PRO": 1160,
        "MicoAir405Mini": 1161,
        "BlitzH7Pro": 1162,
        "BlitzF7Mini": 1163,
        "BlitzF7": 1164,
        "3DR-ASAUAV": 1165,
        "MicoAir743": 1166,
        "BlitzH7Wing": 1168,
        "SDMODELH7V2": 1167,
        "JHEMCUF405WING": 1169,
        "MatekG474": 1170,
        "PhenixH7_lite": 1171,
        "PhenixH7_Pro": 1172,
        "2RAWH743": 1173,
        "X-MAV-AP-H743V2": 1174,
        "BETAFPV_F4_2_3S_20A": 1175,
        "MicoAir743AIOv1": 1176,
        "CrazyF405": 1177,
        "FlywooF405HD_AIOv2": 1180,
        "FlywooH743Pro": 1181,
        "ESP32_PERIPH": 1205,
        "ESP32S3_PERIPH": 1206,
        "CSKY-PMU": 1212,
        "MUPilot": 1222,
        "CBUnmanned-CM405-FC": 1301,
        "KHA_ETH": 1315,
        "FlysparkF4": 1361,
        "CUBEORANGE_PERIPH": 1400,
        "CUBEBLACK_PERIPH": 1401,
        "PIXRACER_PERIPH": 1402,
        "SWBOOMBOARD_PERIPH": 1403,
        "VIMDRONES_FLOW": 1404,
        "VIMDRONES_MOSAIC_X5": 1405,
        "VIMDRONES_MOSAIC_H": 1406,
        "VIMDRONES_PERIPH": 1407,
        "PIXHAWK6X_PERIPH": 1408,
        "CUBERED_PERIPH": 1409,
        "RadiolinkPIX6": 1410,
        "JHEMCU-H743HD": 1411,
        "LongbowF405": 1422,
        "MountainEagleH743": 1444,
        "StellarF4": 1500,
        "GEPRCF745BTHD": 1501,
        "HGLRCF405V4": 1524,
        "F4BY_F427": 1530,
        "MFT-SEMA100": 2000,
        "AET-H743-Basic": 2024,
        "SakuraRC-H743": 2714,
        "KRSHKF7_MINI": 4000,
        "HAKRC_F405": 4200,
        "HAKRC_F405Wing": 4201,
        "AIRVOLUTE_DCS2": 5200,
        "AOCODA-RC-H743DUAL": 5210,
        "AOCODA-RC-F405V3": 5211,
        "UAV-DEV-HAT-H7": 5220,
        "UAV-DEV-NucPilot-H7": 5221,
        "UAV-DEV-M10S-L4": 5222,
        "UAV-DEV-F9P-G4": 5223,
        "UAV-DEV-UM982-G4": 5224,
        "UAV-DEV-M20D-G4": 5225,
        "UAV-DEV-Sensorboard-G4": 5226,
        "UAV-DEV-PWM-G4": 5227,
        "UAV-DEV-AUAV-H7": 5228,
        "UAV-DEV-FC-H7": 5229,
        "TM-SYS-BeastFC": 5240,
        "TM-SYS-Sensornode": 5241,
        "TM-SYS-OpenHDFPV": 5242,
        "TM-SYS-VisualNAV": 5243,
        "TM-SYS-Airspeed": 5244,
        "TBS_LUCID_H7": 5250,
        "TBS_LUCID_PRO": 5251,
        "Sierra-TrueNavPro-G4": 5301,
        "Sierra-TrueNavIC": 5302,
        "Sierra-TrueNorth-G4": 5303,
        "Sierra-TrueSpeed-G4": 5304,
        "Sierra-PrecisionPoint-G4": 5305,
        "Sierra-AeroNex": 5306,
        "Sierra-TrueFlow": 5307,
        "Sierra-TrueNavIC-Pro": 5308,
        "Sierra-F1-Pro": 5309,
        "Holybro-PMU-F4": 5401,
        "Holybro-UM982-G4": 5402,
        "Holybro-UM960-H7": 5403,
        "Holybro-PERIPH-H7": 5404,
        "Holybro-DroneCAN-Airspeed": 5405,
        "Holybro-KakuteF4-Wing": 5406,
        "MATEKH743SE": 5501,
        "ZeroOne_X6": 5600,
        "ZeroOne_PMU": 5601,
        "ZeroOne_GNSS": 5602,
        "DroneBuild_G1": 5700,
        "DroneBuild_G2": 5701,
        "MFE_PDB_CAN": 6100,
        "MFE_POS3_CAN": 6101,
        "MFE_RTK_CAN": 6102,
        "MFE_AirSpeed_CAN": 6103,
        "CUAV-7-NANO": 7000,
        "VUAV-V7pro": 7100,
        "AEROFOX_H7": 7110,
        "CubeOrange_ODID": 10140,
        "Pixhawk6_ODID": 10053,
    }
    return ardupilot_board_ids.get(platform, -1)


def is_valid_elf_type(elf_arch: str) -> bool:
    arch_mapping = {"i386": "x86", "x86_64": "x64", "armv7l": "ARM", "aarch64": "AArch64"}
    system_arch = system_platform.machine()
    system_arch = arch_mapping.get(system_arch, system_arch)

    if system_arch == elf_arch:
        return True
    if system_arch == "AArch64" and elf_arch == "ARM":
        return True
    return False


def get_correspondent_decoder_platform(current_platform: Platform) -> Union[BoardType, BoardSubType]:
    correspondent_decoder_platform = {
        Platform.SITL: BoardType.SITL,
        Platform.Navigator: BoardSubType.LINUX_NAVIGATOR,
        Platform.Argonot: BoardSubType.LINUX_NAVIGATOR,
        Platform.Navigator64: BoardSubType.LINUX_NAVIGATOR,
    }
    return correspondent_decoder_platform.get(current_platform, BoardType.EMPTY)


class FirmwareInstaller:
    """Abstracts the install procedures for different supported boards.

    For proper usage one needs to set the platform before using other methods.

    Args:
        firmware_folder (pathlib.Path): Path for firmware folder.
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def _validate_apj(firmware_path: pathlib.Path, board: FlightController) -> None:
        logger.debug(f"Validating APJ firmware for board {board}.")
        try:
            with open(firmware_path, "r", encoding="utf-8") as firmware_file:
                firmware_data = firmware_file.read()
                firm_board_id = int(json.loads(firmware_data).get("board_id", -1))
            logger.debug(f"firm_board_id: {firm_board_id}")
            expected_board_id = get_board_id(board)
            logger.debug(f"expected_board_id: {expected_board_id}")
            if expected_board_id == -1:
                raise UnsupportedPlatform("Firmware validation is not implemented for this board yet.")
            if firm_board_id == -1:
                raise InvalidFirmwareFile("Could not find board_id specification in the firmware file.")
            if firm_board_id != expected_board_id:
                raise InvalidFirmwareFile(f"Expected board_id {expected_board_id}, found {firm_board_id}.")
            return
        except Exception as error:
            raise InvalidFirmwareFile("Could not load firmware file for validation.") from error

    @staticmethod
    def _validate_elf(firmware_path: pathlib.Path, platform: Platform) -> None:
        # Check if firmware's architecture matches system's architecture
        with open(firmware_path, "rb") as file:
            try:
                elf_file = ELFFile(file)
                firm_arch = elf_file.get_machine_arch()
            except Exception as error:
                raise InvalidFirmwareFile("Given file is not a valid ELF.") from error
        if not is_valid_elf_type(firm_arch):
            raise InvalidFirmwareFile(
                f"Firmware's architecture ({firm_arch}) does not match system's ({system_platform.machine()})."
            )

        # Check if firmware's platform matches system platform
        try:
            firm_decoder = Decoder()
            firm_decoder.process(firmware_path)
            firm_board = BoardType(firm_decoder.fwversion.board_type)
            firm_sub_board = BoardSubType(firm_decoder.fwversion.board_subtype)
            current_decoder_platform = get_correspondent_decoder_platform(platform)
            logger.debug(
                f"firm_board: {firm_board}, firm_sub_board: {firm_sub_board}, current_decoder_platform: {current_decoder_platform}"
            )
            if current_decoder_platform not in [firm_board, firm_sub_board]:
                raise InvalidFirmwareFile(
                    (
                        f"Firmware's platform ({current_decoder_platform}) does not match system's ({platform}),"
                        f"for board ({firm_board}) or sub board ({firm_sub_board})."
                    )
                )
        except Exception as error:
            raise InvalidFirmwareFile("Given firmware is not a supported version.") from error

    @staticmethod
    def validate_firmware(firmware_path: pathlib.Path, board: FlightController) -> None:
        """Check if given firmware is valid for given platform."""
        logger.debug(f"Validating firmware for board {board}.")
        logger.debug(f"platform type: {board.platform.type}")
        firmware_format = FirmwareDownloader._supported_firmware_formats[board.platform.type]
        logger.debug(f"Firmware format: {firmware_format}")
        if firmware_format == FirmwareFormat.APJ:
            FirmwareInstaller._validate_apj(firmware_path, board)
            return

        if firmware_format == FirmwareFormat.ELF:
            FirmwareInstaller._validate_elf(firmware_path, board.platform)
            return
        raise UnsupportedPlatform("Firmware validation is not implemented for this platform.")

    @staticmethod
    def add_run_permission(firmware_path: pathlib.Path) -> None:
        """Add running permission for firmware file."""
        # Make the binary executable
        ## S_IX: Execution permission for
        ##    OTH: Others
        ##    USR: User
        ##    GRP: Group
        ## For more information: https://www.gnu.org/software/libc/manual/html_node/Permission-Bits.html
        os.chmod(firmware_path, firmware_path.stat().st_mode | stat.S_IXOTH | stat.S_IXUSR | stat.S_IXGRP)

    def install_firmware(
        self,
        new_firmware_path: pathlib.Path,
        board: FlightController,
        firmware_dest_path: Optional[pathlib.Path] = None,
    ) -> None:
        """Install given firmware."""
        if not new_firmware_path.is_file():
            raise InvalidFirmwareFile("Given path is not a valid file.")

        logger.debug(f"Installing firmware for board {board}, from {new_firmware_path}.")
        firmware_format = FirmwareDownloader._supported_firmware_formats[board.platform.type]
        if firmware_format == FirmwareFormat.ELF:
            self.add_run_permission(new_firmware_path)

        self.validate_firmware(new_firmware_path, board)

        if board.type == PlatformType.Serial:
            firmware_uploader = FirmwareUploader()
            if not board.path:
                raise ValueError("Board path not available.")
            firmware_uploader.set_autopilot_port(pathlib.Path(board.path))
            firmware_uploader.upload(new_firmware_path)
            return
        if firmware_format == FirmwareFormat.ELF:
            # Using copy() instead of move() since the last can't handle cross-device properly (e.g. docker binds)
            if not firmware_dest_path:
                raise FirmwareInstallFail("Firmware file destination not provided.")
            shutil.copy(new_firmware_path, firmware_dest_path)
            return

        raise UnsupportedPlatform("Firmware install is not implemented for this platform.")
