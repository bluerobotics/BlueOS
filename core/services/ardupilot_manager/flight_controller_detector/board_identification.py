from enum import Enum
from typing import List

from pydantic import BaseModel

from typedefs import Platform


class SerialAttr(str, Enum):
    product = "product"
    manufacturer = "manufacturer"


class SerialBoardIdentifier(BaseModel):
    attribute: SerialAttr
    id_value: str
    platform: Platform


identifiers: List[SerialBoardIdentifier] = [
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="Pixhawk1", platform=Platform.Pixhawk1),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="FMU v2.x", platform=Platform.Pixhawk1),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="FMU v3.x", platform=Platform.Pixhawk1),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="Pixhawk4", platform=Platform.Pixhawk4),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="FMU v5.x", platform=Platform.Pixhawk4),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="FMU v6X.x", platform=Platform.Pixhawk6X),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="FMU v6C.x", platform=Platform.Pixhawk6C),
    SerialBoardIdentifier(attribute=SerialAttr.product, id_value="CubeOrange", platform=Platform.CubeOrange),
    SerialBoardIdentifier(attribute=SerialAttr.manufacturer, id_value="ArduPilot", platform=Platform.GenericSerial),
    SerialBoardIdentifier(attribute=SerialAttr.manufacturer, id_value="Arduino", platform=Platform.GenericSerial),
    SerialBoardIdentifier(attribute=SerialAttr.manufacturer, id_value="3D Robotics", platform=Platform.GenericSerial),
    SerialBoardIdentifier(attribute=SerialAttr.manufacturer, id_value="Hex/ProfiCNC", platform=Platform.GenericSerial),
    SerialBoardIdentifier(attribute=SerialAttr.manufacturer, id_value="Holybro", platform=Platform.GenericSerial),
]
