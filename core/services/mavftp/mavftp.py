# As this file is basically copied over from https://github.com/ArduPilot/MAVProxy/blob/master/MAVProxy/modules/mavproxy_ftp.py
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments

import random
import struct
import time
from dataclasses import dataclass
from enum import Enum
from io import BufferedRandom
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ftp_op import (
    FTP_OP,
    OP_Ack,
    OP_BurstReadFile,
    OP_ListDirectory,
    OP_Nack,
    OP_OpenFileRO,
    OP_ReadFile,
    OP_TerminateSession,
)


@dataclass
class DirectoryEntry:
    name: str
    is_dir: bool
    size_b: int


# error codes
class FtpErrors(Enum):
    ERR_None = 0
    ERR_Fail = 1
    ERR_FailErrno = 2
    ERR_InvalidDataSize = 3
    ERR_InvalidSession = 4
    ERR_NoSessionsAvailable = 5
    ERR_EndOfFile = 6
    ERR_UnknownCommand = 7
    ERR_FileExists = 8
    ERR_FileProtected = 9
    ERR_FileNotFound = 10


HDR_Len = 12
MAX_Payload = 239


class Task:
    def __init__(self, ftp: "FTPModule") -> None:
        self.ftp = ftp
        self.op_start: Optional[float] = 0
        self.open_retries = 0
        self.ftp_settings = ftp.ftp_settings

    def extra_idle_tasks(self) -> None:
        pass

    def idle_task(self) -> None:
        """check for file gaps and lost requests"""
        now = time.time()
        # see if we lost an open reply
        assert self.ftp.last_op is not None
        if self.op_start is not None and now - self.op_start > 1.0 and self.ftp.last_op.opcode == OP_OpenFileRO:
            self.op_start = now
            self.open_retries += 1
            if self.open_retries > 2:
                # fail the get
                self.op_start = None
                logger.info("terminating session6")
                self.ftp.terminate_session()
                return
            logger.debug("FTP: retry open")
            send_op = self.ftp.last_op
            self.ftp.send(FTP_OP(self.ftp.seq, self.ftp.session, OP_TerminateSession, 0, 0, 0, 0, None))
            self.session = (self.ftp.session + 1) % 256
            send_op.session = self.session
            self.ftp.send(send_op)
        self.extra_idle_tasks()


class ListHandler(Task):
    def __init__(self, ftp: "FTPModule") -> None:
        super().__init__(ftp)
        self.list_result: List[DirectoryEntry] = []
        self.list_temp_result: List[DirectoryEntry] = []
        self.dir_offset = 0
        self.temp_filename = "/tmp/mavftp_get_file"

    def list(self, path: str) -> List[DirectoryEntry]:
        self.done = False
        self.list_temp_result = []
        self.list_result = []
        self.ftp.list_result = None
        logger.info(f"Listing {path}")
        enc_dname = bytearray(path, "ascii")
        self.dir_offset = 0
        op = FTP_OP(
            self.ftp.seq,
            self.ftp.session,
            OP_ListDirectory,
            len(enc_dname),
            0,
            0,
            self.dir_offset,
            enc_dname,
        )
        for attempt in range(5):
            logger.trace(f"Requesting {path}, attempt {attempt}")
            self.ftp.send(op)
            timeout = time.time() + 2
            while len(self.list_result) == 0 and time.time() < timeout:
                try:
                    m = self.ftp.mav.recv_match(
                        type="FILE_TRANSFER_PROTOCOL",
                        blocking=True,
                        timeout=0.2,
                    )
                    if m is None:
                        self.idle_task()
                        continue
                    timeout = time.time() + 1
                    self.ftp.mavlink_packet(m)
                except TypeError as e:
                    logger.error(e)
                self.idle_task()
                time.sleep(0.0001)
            if len(self.list_result) > 0:
                break

        return self.list_result

    def handle_list_reply(self, op: FTP_OP, _m: Any) -> None:
        logger.info("handling list reply")
        output: List[DirectoryEntry] = []
        if op.opcode == OP_Ack and op.payload is not None:
            dentries = sorted(op.payload.split(b"\x00"))
            for d in dentries:
                if len(d) == 0:
                    continue
                self.dir_offset += 1
                try:
                    dir_entry = str(d, "ascii")
                except Exception as error:
                    logger.debug(error)
                    continue
                if dir_entry[0] == "D":
                    output.append(DirectoryEntry(name=dir_entry[1:], is_dir=True, size_b=0))
                elif dir_entry[0] == "F":
                    (name, size_str) = dir_entry[1:].split("\t")
                    size = int(size_str)
                    output.append(DirectoryEntry(name=name, size_b=size, is_dir=False))
                else:
                    pass
            # ask for more, should we just create a new op?
            more = self.ftp.last_op
            assert isinstance(more, FTP_OP)
            if more is not None:
                more.offset = self.dir_offset
            self.ftp.send(more)
        elif op.opcode == OP_Nack and op.payload is not None and len(op.payload) == 1 and op.payload[0] == 6:
            self.list_result = self.list_temp_result
        self.list_temp_result.extend(output)


class ReadHandler(Task):
    # pylint: disable=too-many-instance-attributes
    def __init__(self, ftp: "FTPModule") -> None:
        super().__init__(ftp)
        self.op_start: Optional[float] = 0
        self.filename: Optional[str] = None
        self.read_total = 0
        self.read_gaps: List[Tuple[int, int]] = []
        self.read_gap_times: Dict[Any, float] = {}
        self.last_gap_send: float = 0
        self.reached_eof = True
        self.done = False
        self.backlog = 0
        self.last_burst_read: Optional[float] = None
        self.fh: Optional[BufferedRandom] = None
        self.temp_filename = "/tmp/mavftp_get_file"
        self.burst_size: int = 239
        self.get_result: Optional[bytes] = None

    def extra_idle_tasks(self) -> None:
        now = time.time()
        if len(self.read_gaps) == 0 and self.last_burst_read is None:
            return

        if self.fh is None:
            return

        # see if burst read has stalled
        if (
            not self.reached_eof
            and self.last_burst_read is not None
            and now - self.last_burst_read > self.ftp_settings["retry_time"]
        ):
            dt = now - self.last_burst_read
            self.last_burst_read = now
            logger.debug(f"Retry read at {self.fh.tell()} rtt={self.ftp.rtt:.2f} dt={dt:.2f}")
            self.ftp.send(
                FTP_OP(
                    self.ftp.seq,
                    self.ftp.session,
                    OP_BurstReadFile,
                    self.burst_size,
                    0,
                    0,
                    self.fh.tell(),
                    None,
                )
            )

        # see if we can fill gaps
        self.check_read_send()

    def read_sector(self, path: str, offset: int, size: int) -> Optional[bytes]:
        logger.info(f"reading sector {path}, offset={offset}, size={size}")
        return self.read(path, size, offset)

    def read(self, path: str, size: int, offset: int = 0) -> Optional[bytes]:
        """get file"""
        self.get_result = None
        self.requested_offset = offset
        self.requested_size = size
        self.filename = path
        self.done = False

        logger.info(f"Getting {path} starting at {self.requested_offset}, reading {self.requested_size} bytes")

        self.op_start = time.time()
        self.read_total = 0
        self.reached_eof = False
        self.burst_size = int(self.ftp_settings["burst_read_size"])
        if self.burst_size < 1:
            self.burst_size = 239
        elif self.burst_size > 239:
            self.burst_size = 239
        enc_fname = bytearray(path, "ascii")
        self.open_retries = 0
        op = FTP_OP(self.ftp.seq, self.ftp.session, OP_OpenFileRO, len(enc_fname), 0, 0, 0, enc_fname)
        self.ftp.send(op)
        timeout = time.time() + 5
        while not self.done and time.time() < timeout:
            try:
                m = self.ftp.mav.recv_match(
                    type="FILE_TRANSFER_PROTOCOL",
                    blocking=True,
                    timeout=1.0,
                )
                if m is None:
                    self.idle_task()
                    continue
                timeout = time.time() + 5
                self.ftp.mavlink_packet(m)
            except TypeError as e:
                logger.error(e)
            self.idle_task()
            time.sleep(0.0001)
        logger.info(f"loop closed, gaps:{self.read_gaps}, done: {self.done}")
        if len(self.read_gaps) == 0:
            return self.get_result
        logger.error(f"closed read with {self.read_gaps} gaaps")
        return None

    def handle_open_RO_reply(self, op: FTP_OP, _m: Any) -> None:
        """handle OP_OpenFileRO reply"""
        try:
            if op.opcode == OP_Ack:
                logger.info("file opened successfully")
                # pylint: disable=consider-using-with
                self.fh = open(self.temp_filename, "wb+")
                self.fh.truncate(0)
                self.fh.seek(self.requested_offset)
                read = FTP_OP(
                    self.ftp.seq, self.ftp.session, OP_BurstReadFile, self.burst_size, 0, 0, self.requested_offset, None
                )

                self.last_burst_read = time.time()
                self.ftp.send(read)
            else:
                logger.error("ftp open failed")
                self.ftp.terminate_session()
        except Exception as e:
            logger.error(e)

    def handle_reply_read(self, op: FTP_OP, _m: Any) -> None:
        """handle OP_ReadFile reply"""
        logger.info("handle reply read")
        if self.backlog > 0:
            self.backlog -= 1
        if op.opcode == OP_Ack and self.fh is not None:
            gap = (op.offset, op.size)
            if gap in self.read_gaps:
                self.read_gaps.remove(gap)
                self.read_gap_times.pop(gap)
                self.write_payload(op)
                logger.debug(f"FTP: removed gap {gap}, {self.reached_eof}, {len(self.read_gaps)}")
                if self.check_read_finished():
                    return
            elif op.size < self.burst_size:
                logger.debug(f"FTP: file size changed to {op.offset + op.size}")
                self.ftp.terminate_session()
            else:
                logger.trace("FTP: no gap read", gap, len(self.read_gaps))
        elif op.opcode == OP_Nack:
            logger.debug(f"Read failed with {len(self.read_gaps)} gaps : {str(op)}")
            self.ftp.terminate_session()
        self.check_read_send()

    def handle_burst_read(self, op: FTP_OP, _m: Any) -> None:
        """handle OP_BurstReadFile reply"""
        logger.trace("handle burst read")
        if self.ftp_settings["pkt_loss_tx"] > 0:
            if random.uniform(0, 100) < self.ftp_settings["pkt_loss_tx"]:
                logger.trace("FTP: dropping TX")
                return
        if self.fh is None or self.filename is None:
            if op.session != self.ftp.session:
                # old session
                return
            logger.error("FTP Unexpected burst read reply")
            logger.info(op)
            return
        self.last_burst_read = time.time()
        assert op.payload is not None
        size = len(op.payload)
        if size > self.burst_size:
            # this server doesn't handle the burst size argument
            self.burst_size = MAX_Payload
            logger.debug(f"Setting burst size to {self.burst_size}")
        if op.opcode == OP_Ack and self.fh is not None:
            ofs = self.fh.tell()
            if op.offset < ofs:
                # writing an earlier portion, possibly remove a gap
                gap = (op.offset, len(op.payload))
                if gap in self.read_gaps:
                    self.read_gaps.remove(gap)
                    self.read_gap_times.pop(gap)
                    logger.debug(
                        "FTP: removed gap",
                        gap,
                        self.reached_eof,
                        len(self.read_gaps),
                    )
                else:

                    logger.debug(f"FTP: dup read reply at {op.offset} of len {op.size} ofs={self.fh.tell()}")
                    return
                self.write_payload(op)
                if self.check_read_finished():
                    logger.info("Read finished")
                    return
            elif op.offset > ofs and op.offset < self.requested_offset + self.requested_size:
                # we have a gap
                gap = (ofs, op.offset - ofs)
                max_read = self.burst_size
                while True:
                    if gap[1] <= max_read:
                        self.read_gaps.append(gap)
                        self.read_gap_times[gap] = 0
                        break
                    g = (gap[0], max_read)
                    self.read_gaps.append(g)
                    self.read_gap_times[g] = 0
                    gap = (gap[0] + max_read, gap[1] - max_read)
                self.write_payload(op)
            else:
                self.write_payload(op)
            if op.burst_complete:
                if op.size > 0 and op.size < self.burst_size:
                    # a burst complete with non-zero size and less than burst packet size
                    # means EOF
                    assert self.op_start is not None
                    if not self.reached_eof:
                        logger.trace(
                            f"EOF at {self.fh.tell()} with {len(self.read_gaps)} gaps t={time.time() - self.op_start:.2f}"
                        )
                    self.reached_eof = True
                    if self.check_read_finished():
                        return
                    self.check_read_send()
                    return
                if self.read_total >= self.requested_size:
                    self.check_read_finished()
                    return
                assert self.ftp.last_op is not None
                more = self.ftp.last_op
                more.offset = op.offset + op.size
                logger.debug(f"FTP: burst continue at {more.offset} {self.fh.tell()}")
                self.ftp.send(more)
        elif op.opcode == OP_Nack:
            ecode = op.payload[0]
            logger.debug(f"FTP: burst nack: {op}")
            if ecode in [6, 0]:
                if not self.reached_eof and op.offset > self.fh.tell():
                    # we lost the last part of the burst
                    logger.debug(f"burst lost EOF {self.fh.tell()} {op.offset}")
                    return
                assert self.op_start is not None
                if not self.reached_eof:
                    logger.debug(
                        f"EOF at {self.fh.tell()} with {len(self.read_gaps)} gaps t={time.time() - self.op_start:.2f}"
                    )
                self.reached_eof = True
                if self.check_read_finished():
                    return
                self.check_read_send()
            else:
                logger.debug(f"FTP: burst Nack (ecode:{ecode}): {op}")
        else:
            logger.debug(f"FTP: burst error: {op}")

    def idle_task(self) -> None:
        """check for file gaps and lost requests"""
        now = time.time()
        # see if we lost an open reply
        assert self.ftp.last_op is not None
        if self.op_start is not None and now - self.op_start > 1.0 and self.ftp.last_op.opcode == OP_OpenFileRO:
            self.op_start = now
            self.open_retries += 1
            if self.open_retries > 2:
                # fail the get
                self.op_start = None
                logger.info("terminating session6")
                self.ftp.terminate_session()
                return
            logger.debug("FTP: retry open")
            send_op = self.ftp.last_op
            self.ftp.send(FTP_OP(self.ftp.seq, self.ftp.session, OP_TerminateSession, 0, 0, 0, 0, None))
            self.session = (self.ftp.session + 1) % 256
            send_op.session = self.session
            self.ftp.send(send_op)

        if len(self.read_gaps) == 0 and self.last_burst_read is None:
            return

        if self.fh is None:
            return

        # see if burst read has stalled
        if (
            not self.reached_eof
            and self.last_burst_read is not None
            and now - self.last_burst_read > self.ftp_settings["retry_time"]
        ):
            dt = now - self.last_burst_read
            self.last_burst_read = now
            logger.debug(f"Retry read at {self.fh.tell()} rtt={self.ftp.rtt:.2f} dt={dt:.2f}")
            self.ftp.send(
                FTP_OP(
                    self.ftp.seq,
                    self.ftp.session,
                    OP_BurstReadFile,
                    self.burst_size,
                    0,
                    0,
                    self.fh.tell(),
                    None,
                )
            )

        # see if we can fill gaps
        self.check_read_send()

    def check_read_finished(self) -> bool:
        """check if download has completed"""
        if self.fh is None:
            return True
        if self.op_start is None:
            return True
        if len(self.read_gaps) == 0 and (self.reached_eof or self.read_total >= self.requested_size):
            ofs = self.fh.tell()
            dt = time.time() - self.op_start
            rate = (self.read_total / dt) / 1024.0
            logger.info(
                f"Wrote {self.read_total}/{self.requested_size} bytes to {self.filename} in {dt:.2f}s {rate:.1f}kByte/s"
            )
            logger.info(f"terminating with {self.read_total} out of {self.requested_size} (ofs={ofs})")
            self.done = True

            assert self.fh is not None
            self.fh.seek(0)
            result = self.fh.read()
            self.get_result = result[self.requested_offset : self.requested_offset + self.requested_size]
            assert self.get_result is not None
            if len(self.get_result) <= self.requested_size:
                logger.warning(f"expected {self.requested_size}, got {len(self.get_result)}")
            logger.info(f"read {len(self.get_result)} bytes")
            self.ftp.terminate_session()

            self.fh.flush()
            self.fh.close()
            return True
        return False

    def send_gap_read(self, g: Tuple[int, int]) -> None:
        """send a read for a gap"""
        (offset, length) = g
        logger.info(f"send_gap_read {g}")
        logger.debug(f"Gap read of {length} at {offset} rem={len(self.read_gaps)} blog={self.backlog}")
        read = FTP_OP(self.ftp.seq, self.ftp.session, OP_ReadFile, length, 0, 0, offset, None)
        self.ftp.send(read)
        self.read_gaps.remove(g)
        self.read_gaps.append(g)
        self.last_gap_send = time.time()
        self.read_gap_times[g] = self.last_gap_send
        self.backlog += 1

    def check_read_send(self) -> None:
        """see if we should send another gap read"""
        if len(self.read_gaps) == 0:
            return
        g = self.read_gaps[0]
        now = time.time()
        dt = now - self.read_gap_times[g]
        if not self.reached_eof:
            # send gap reads once
            for gap, times in self.read_gap_times.items():
                if times == 0:
                    self.send_gap_read(gap)
            return
        if self.read_gap_times[g] > 0 and dt > self.ftp_settings["retry_time"]:
            if self.backlog > 0:
                self.backlog -= 1
            self.read_gap_times[g] = 0

        if self.read_gap_times[g] != 0:
            # still pending
            return
        if now - self.last_gap_send < 0.05:
            # don't send too fast
            return
        self.send_gap_read(g)

    def write_payload(self, op: FTP_OP) -> None:
        """write payload from a read op"""
        if self.fh is None:
            raise RuntimeError("No file handle")
        if not op.payload:
            raise RuntimeError("No payload")
        current_ofs = self.fh.tell()
        if op.offset != current_ofs:
            logger.warning(f"offset mismatch: {op.offset} != {current_ofs} = {op.offset - current_ofs}")
        self.fh.seek(op.offset)
        self.fh.write(op.payload)
        self.read_total += len(op.payload)
        logger.trace(f"read {len(op.payload)} bytes at {op.offset} total={self.read_total}")


class FTPModule:
    def __init__(self, mav: Any) -> None:

        self.ftp_settings = {
            "pkt_loss_tx": 0.0,
            "pkt_loss_rx": 0.0,
            "max_backlog": 5,
            "burst_read_size": 239,
            "retry_time": 0.2,
        }
        self.list_handler = ListHandler(self)
        self.read_handler = ReadHandler(self)
        self.seq = 0
        self.session = 0
        self.network = 0
        self.last_op: Optional[FTP_OP] = None
        self.filename = Optional[str]
        self.op_start: Optional[float] = None
        self.last_op_time = time.time()
        self.rtt = 0.5
        self.backlog = 0
        self.burst_size = int(self.ftp_settings["burst_read_size"])
        self.mav = mav
        self.target_system = 0
        self.target_component = 0
        self.get_result = Optional[bytearray]
        self.list_result = Optional[list[dict[str, Any]]]
        msg = None
        logger.info("waiting for connection")
        while not msg:
            self.mav.mav.ping_send(
                int(time.time() * 1e6),  # Unix time in microseconds
                0,  # Ping number
                0,  # Request ping of all systems
                0,  # Request ping of all components
            )
            msg = self.mav.recv_match()
            if msg:
                logger.info("connected")
                break

    def send(self, op: FTP_OP) -> None:
        """send a request"""
        op.seq = self.seq
        payload = op.pack()
        plen = len(payload)
        if plen < MAX_Payload + HDR_Len:
            payload.extend(bytearray([0] * ((HDR_Len + MAX_Payload) - plen)))
        self.mav.mav.file_transfer_protocol_send(self.network, self.target_system, self.target_component, payload)
        self.seq = (self.seq + 1) % 256
        self.last_op = op
        now = time.time()
        logger.trace(f"> {op} dt={now - self.last_op_time:.2f}")
        self.last_op_time = time.time()

    def terminate_session(self) -> None:
        """terminate current session"""
        logger.info("session terminated")
        self.send(FTP_OP(self.seq, self.session, OP_TerminateSession, 0, 0, 0, 0, None))
        self.read_total = 0
        self.last_burst_read: float = 0
        self.session = (self.session + 1) % 256
        self.reached_eof = False
        self.backlog = 0
        logger.debug("Terminated session")

    def read_sector(self, path: str, offset: int, size: int) -> Optional[bytes]:
        return self.read_handler.read_sector(path, offset, size)

    def list(self, path: str) -> List[DirectoryEntry]:
        """list files"""
        return self.list_handler.list(path)

    def op_parse(self, m: Any) -> FTP_OP:
        """parse a FILE_TRANSFER_PROTOCOL msg"""
        hdr = bytearray(m.payload[0:12])
        (
            seq,
            session,
            opcode,
            size,
            req_opcode,
            burst_complete,
            _pad,
            offset,
        ) = struct.unpack("<HBBBBBBI", hdr)
        payload = bytearray(m.payload[12:])[:size]
        return FTP_OP(seq, session, opcode, size, req_opcode, burst_complete, offset, payload)

    def mavlink_packet(self, m: Any) -> None:
        """handle a mavlink packet"""
        mtype = m.get_type()
        if mtype == "FILE_TRANSFER_PROTOCOL":
            op = self.op_parse(m)
            now = time.time()
            dt = now - self.last_op_time
            logger.trace(f"< {op} dt={dt:.2f}")
            self.last_op_time = now
            if self.ftp_settings["pkt_loss_rx"] > 0:
                if random.uniform(0, 100) < self.ftp_settings["pkt_loss_rx"]:
                    logger.debug("FTP: dropping packet RX")
                    return
            if op.opcode == OP_Nack:
                assert op.payload is not None
                code = op.payload[0]
                logger.error(f"FTP_ERROR: {FtpErrors(code).name}")
            if (
                self.last_op is not None
                and op.req_opcode == self.last_op.opcode
                and op.seq == (self.last_op.seq + 1) % 256
            ):
                self.rtt = max(min(self.rtt, dt), 0.01)
            if op.req_opcode == OP_ListDirectory:
                self.list_handler.handle_list_reply(op, m)
            elif op.req_opcode == OP_OpenFileRO:
                self.read_handler.handle_open_RO_reply(op, m)
            elif op.req_opcode == OP_BurstReadFile:
                self.read_handler.handle_burst_read(op, m)
            elif op.req_opcode == OP_ReadFile:
                self.read_handler.handle_reply_read(op, m)
            else:
                logger.error(f"FTP Unknown {str(op)}")
