class PX4Board:
    boards_id_to_firmware_name_mapping = {
        9: "px4_fmu-v2_default",
        255: "px4_fmu-v3_default",
        11: "px4_fmu-v4_default",
        13: "px4_fmu-v4pro_default",
        20: "uvify_core_default",
        50: "px4_fmu-v5_default",
        51: "px4_fmu-v5x_default",
        52: "px4_fmu-v6_default",
        53: "px4_fmu-v6x_default",
        54: "px4_fmu-v6u_default",
        56: "px4_fmu-v6c_default",
        57: "ark_fmu-v6x_default",
        35: "px4_fmu-v6xrt_default",
        55: "sky-drones_smartap-airlink_default",
        88: "airmind_mindpx-v2_default",
        12: "bitcraze_crazyflie_default",
        14: "bitcraze_crazyflie21_default",
        42: "omnibus_f4sd_default",
        33: "mro_x21_default",
        65: "intel_aerofc-v1_default",
        123: "holybro_kakutef7_default",
        41775: "modalai_fc-v1_default",
        41776: "modalai_fc-v2_default",
        78: "holybro_pix32v5_default",
        79: "holybro_can-gps-v1_default",
        28: "nxp_fmuk66-v3_default",
        30: "nxp_fmuk66-e_default",
        31: "nxp_fmurt1062-v1_default",
        85: "freefly_can-rtk-gps_default",
        120: "cubepilot_cubeyellow_default",
        136: "mro_x21-777_default",
        139: "holybro_durandal-v1_default",
        140: "cubepilot_cubeorange_default",
        1063: "cubepilot_cubeorangeplus_default",
        141: "mro_ctrl-zero-f7_default",
        142: "mro_ctrl-zero-f7-oem_default",
        212: "thepeach_k1_default",
        213: "thepeach_r1_default",
        1009: "cuav_nora_default",
        1010: "cuav_x7pro_default",
        1017: "mro_pixracerpro_default",
        1022: "mro_ctrl-zero-classic_default",
        1023: "mro_ctrl-zero-h7_default",
        1024: "mro_ctrl-zero-h7-oem_default",
        1048: "holybro_kakuteh7_default",
        1053: "holybro_kakuteh7v2_default",
        1054: "holybro_kakuteh7mini_default",
        1110: "jfb_jfb110_default",
    }

    def __init__(self, board_id: int, name: str) -> None:
        self.id = board_id
        self.name = name

    @classmethod
    def from_id(cls, board_id: int) -> "PX4Board":
        board_name = cls.boards_id_to_firmware_name_mapping.get(board_id, None)
        if board_name is None:
            raise ValueError(f"Board with id {board_id} not found")

        return cls(board_id, board_name)
