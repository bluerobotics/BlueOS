import asyncio
import glob
import os
import socket
import time
from pathlib import Path
from typing import Optional, Tuple, Union

from loguru import logger

from exceptions import BusyError, NetworkAddFail, SockCommError, WPAOperationFail


class WPASupplicant:
    BUFFER_SIZE = 4096
    target: Union[Tuple[str, int], str] = ("localhost", 6664)

    def __init__(self) -> None:
        self.sock: Optional[socket.socket] = None

    def __del__(self) -> None:
        if self.sock:
            self.sock.close()

    def run(self, target: Union[Tuple[str, int], str] = target) -> None:
        """Does the connection and setup variables

        Arguments:
            path {[tuple/str]} -- Can be a tuple to connect (ip/port) or unix socket file
        """
        self.target = target

        wpa_playground_path = "/tmp/wpa_playground"
        Path(wpa_playground_path).mkdir(parents=True, exist_ok=True)

        if isinstance(self.target, tuple):
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            # clear path
            files = glob.glob(f"{wpa_playground_path}/*")
            for f in files:
                os.remove(f)
            socket_client = f"{wpa_playground_path}/wpa_supplicant_service_{os.getpid()}"
            self.sock.bind(socket_client)

        self.sock.settimeout(10)
        self.sock.connect(self.target)

    async def send_command(self, command: str, timeout: float) -> bytes:
        """Send a specific WPA Supplicant command.
        Raises if the command fails to answer before the specified timeout.

        Arguments:
            command {str} -- WPA Supplicant command to be sent
            timeout {float} -- Maximum time (in seconds) allowed for receiving an answer before raising a BusyError
        """
        assert self.sock, "No socket assigned to WPA Supplicant"

        timeout_start = time.time()
        while time.time() - timeout_start < timeout:
            try:
                self.sock.send(command.encode("utf-8"))
                data, _ = self.sock.recvfrom(self.BUFFER_SIZE)
            except Exception as error:
                # Oh my, something is wrong!
                # For now, let us report the error but not without recreating the socket
                error_message = "Could not communicate with WPA Supplicant socket"
                try:
                    logger.warning(f"{error_message}: {error}")
                    logger.warning("Trying to recover and recreate socket..")
                    self.run(self.target)
                except Exception as inner_error:
                    logger.error(f"Failed to send command and failed to recreate wpa socket: {inner_error}")
                raise SockCommError(error_message) from error

            if b"FAIL-BUSY" in data:
                logger.info(f"Busy during {command} operation. Trying again...")
                await asyncio.sleep(0.1)
                continue
            break
        else:
            raise BusyError(f"{command} operation took more than specified timeout ({timeout}). Cancelling.")

        if data == b"FAIL":
            raise WPAOperationFail(f"WPA operation {command} failed.")

        return data

    async def send_command_ping(self, timeout: float = 1) -> bytes:
        """Send message: PING

        This command can be used to test whether wpa_supplicant is replying to
            the control interface commands. The expected reply is  <code>PONG</code>
            if the connection is open and wpa_supplicant is processing commands.

        """
        return await self.send_command("PING", timeout)

    async def send_command_mib(self, timeout: float = 1) -> bytes:
        """Send message: MIB

        Request a list of MIB variables (dot1x, dot11). The output is a text block
            with each line in  <code>variable=value</code>  format. For example:

        """
        return await self.send_command("MIB", timeout)

    async def send_command_status(self, timeout: float = 1) -> bytes:
        """Send message: STATUS

        Request current WPA/EAPOL/EAP status information. The output is a text
            block with each line in  <code>variable=value</code>  format. For
            example:
        """
        return await self.send_command("STATUS", timeout)

    async def send_command_status_verbose(self, timeout: float = 1) -> bytes:
        """Send message: STATUS-VERBOSE

        Same as STATUS, but with more verbosity (i.e., more  <code>variable=value</code>
            pairs).
        """
        return await self.send_command("STATUS-VERBOSE", timeout)

    async def send_command_pmksa(self, timeout: float = 1) -> bytes:
        """Send message: PMKSA

        Show PMKSA cache
        """
        return await self.send_command("PMKSA", timeout)

    async def send_command_set(self, variable: str, value: str, timeout: float = 1) -> bytes:
        """Send message: SET

        Example command:
        """
        return await self.send_command(f"SET {variable} {value}", timeout)

    async def send_command_logon(self, timeout: float = 1) -> bytes:
        """Send message: LOGON

        IEEE 802.1X EAPOL state machine logon.
        """
        return await self.send_command("LOGON", timeout)

    async def send_command_logoff(self, timeout: float = 1) -> bytes:
        """Send message: LOGOFF

        IEEE 802.1X EAPOL state machine logoff.
        """
        return await self.send_command("LOGOFF", timeout)

    async def send_command_reassociate(self, timeout: float = 1) -> bytes:
        """Send message: REASSOCIATE

        Force reassociation.
        """
        return await self.send_command("REASSOCIATE", timeout)

    async def send_command_reconnect(self, timeout: float = 1) -> bytes:
        """Send message: RECONNECT

        Connect if disconnected (i.e., like  <code>REASSOCIATE</code> , but only
            connect if in disconnected state).
        """
        return await self.send_command("RECONNECT", timeout)

    async def send_command_preauth(self, BSSID: str, timeout: float = 1) -> bytes:
        """Send message: PREAUTH

        Start pre-authentication with the given BSSID.
        """
        return await self.send_command(f"PREAUTH {BSSID}", timeout)

    async def send_command_attach(self, timeout: float = 1) -> bytes:
        """Send message: ATTACH

        Attach the connection as a monitor for unsolicited events. This can be
            done with  <a class="el" href="wpa__ctrl_8c.html#a3257febde163010311f3306ac0468257">wpa_ctrl_attach()</a>
            .
        """
        return await self.send_command("ATTACH", timeout)

    async def send_command_detach(self, timeout: float = 1) -> bytes:
        """Send message: DETACH

        Detach the connection as a monitor for unsolicited events. This can be
            done with  <a class="el" href="wpa__ctrl_8c.html#ae326ca921d06153e4efce717ae5dd4da">wpa_ctrl_detach()</a>
            .
        """
        return await self.send_command("DETACH", timeout)

    async def send_command_level(self, debug_level: str, timeout: float = 1) -> bytes:
        """Send message: LEVEL

        Change debug level.
        """
        return await self.send_command(f"LEVEL {debug_level}", timeout)

    async def send_command_reconfigure(self, timeout: float = 1) -> bytes:
        """Send message: RECONFIGURE

        Force wpa_supplicant to re-read its configuration data.
        """
        return await self.send_command("RECONFIGURE", timeout)

    async def send_command_terminate(self, timeout: float = 1) -> bytes:
        """Send message: TERMINATE

        Terminate wpa_supplicant process.
        """
        return await self.send_command("TERMINATE", timeout)

    async def send_command_bssid(self, network_id: int, BSSID: str, timeout: float = 1) -> bytes:
        """Send message: BSSID

        Set preferred BSSID for a network. Network id can be received from the
            <code>LIST_NETWORKS</code>  command output.
        """
        return await self.send_command(f"BSSID {network_id} {BSSID}", timeout)

    async def send_command_list_networks(self, timeout: float = 1) -> bytes:
        """Send message: LIST_NETWORKS

        (note: fields are separated with tabs)
        """
        return await self.send_command("LIST_NETWORKS", timeout)

    async def send_command_disconnect(self, timeout: float = 1) -> bytes:
        """Send message: DISCONNECT

        Disconnect and wait for  <code>REASSOCIATE</code>  or  <code>RECONNECT</code>
            command before connecting.
        """
        return await self.send_command("DISCONNECT", timeout)

    async def send_command_scan(self, timeout: float = 1) -> bytes:
        """Send message: SCAN

        Request a new BSS scan.
        """
        return await self.send_command("SCAN", timeout)

    async def send_command_scan_results(self, timeout: float = 1) -> bytes:
        """Send message: SCAN_RESULTS

        (note: fields are separated with tabs)
        """
        return await self.send_command("SCAN_RESULTS", timeout)

    async def send_command_bss(self, timeout: float = 1) -> bytes:
        """Send message: BSS

        BSS information is presented in following format. Please note that new
            fields may be added to this field=value data, so the ctrl_iface
            user should be prepared to ignore values it does not understand.

        """
        return await self.send_command("BSS", timeout)

    async def send_command_select_network(self, network_id: int, timeout: float = 1) -> bytes:
        """Send message: SELECT_NETWORK

        Select a network (disable others). Network id can be received from the
            <code>LIST_NETWORKS</code>  command output.
        """
        return await self.send_command(f"SELECT_NETWORK {network_id}", timeout)

    async def send_command_enable_network(self, network_id: int, timeout: float = 1) -> bytes:
        """Send message: ENABLE_NETWORK

        Enable a network. Network id can be received from the  <code>LIST_NETWORKS</code>
            command output. Special network id  <code>all</code>  can be used
            to enable all network.
        """
        return await self.send_command(f"ENABLE_NETWORK {network_id}", timeout)

    async def send_command_disable_network(self, network_id: int, timeout: float = 1) -> bytes:
        """Send message: DISABLE_NETWORK

        Disable a network. Network id can be received from the  <code>LIST_NETWORKS</code>
            command output. Special network id  <code>all</code>  can be used
            to disable all network.
        """
        return await self.send_command(f"DISABLE_NETWORK {network_id}", timeout)

    async def send_command_add_network(self, timeout: float = 1) -> int:
        """Send message: ADD_NETWORK

        Add a new network. This command creates a new network with empty configuration.
            The new network is disabled and once it has been configured it
            can be enabled with  <code>ENABLE_NETWORK</code>  command.  <code>ADD_NETWORK</code>
            returns the network id of the new network or FAIL on failure.

        """
        network_id = await self.send_command("ADD_NETWORK", timeout)
        if not network_id.strip().isdigit():
            raise NetworkAddFail("Add_network operation did not return a valid id.")
        return int(network_id.strip())

    async def send_command_remove_network(self, network_id: int, timeout: float = 1) -> bytes:
        """Send message: REMOVE_NETWORK

        Remove a network. Network id can be received from the  <code>LIST_NETWORKS</code>
            command output. Special network id  <code>all</code>  can be used
            to remove all network.
        """
        return await self.send_command(f"REMOVE_NETWORK {network_id}", timeout)

    async def send_command_set_network(self, network_id: int, variable: str, value: str, timeout: float = 1) -> bytes:
        """Send message: SET_NETWORK

        This command uses the same variables and data formats as the configuration
            file. See example wpa_supplicant.conf for more details.
        """
        return await self.send_command(f"SET_NETWORK {network_id} {variable} {value}", timeout)

    async def send_command_get_network(self, network_id: int, variable: str, timeout: float = 1) -> bytes:
        """Send message: GET_NETWORK

        Get network variables. Network id can be received from the  <code>LIST_NETWORKS</code>
            command output.
        """
        return await self.send_command(f"GET_NETWORK {network_id} {variable}", timeout)

    async def send_command_save_config(self, timeout: float = 1) -> bytes:
        """Send message: SAVE_CONFIG

        Save the current configuration.
        """
        return await self.send_command("SAVE_CONFIG", timeout)

    async def send_command_p2p_find(self, timeout: float = 1) -> bytes:
        """Send message: P2P_FIND

        The default search type is to first run a full scan of all channels and
            then continue scanning only social channels (1, 6, 11). This behavior
            can be changed by specifying a different search type: social (e.g.,
            "P2P_FIND 5 type=social") will skip the initial full scan and only
            search social channels; progressive (e.g., "P2P_FIND type=progressive")
            starts with a full scan and then searches progressively through
            all channels one channel at the time with the social channel scans.
            Progressive device discovery can be used to find new groups (and
            groups that were not found during the initial scan, e.g., due to
            the GO being asleep) over time without adding considerable extra
            delay for every Search state round.
        """
        return await self.send_command("P2P_FIND", timeout)

    async def send_command_p2p_stop_find(self, timeout: float = 1) -> bytes:
        """Send message: P2P_STOP_FIND

        Stop ongoing P2P device discovery or other operation (connect, listen mode).

        """
        return await self.send_command("P2P_STOP_FIND", timeout)

    async def send_command_p2p_connect(self, timeout: float = 1) -> bytes:
        """Send message: P2P_CONNECT

        The optional "go_intent" parameter can be used to override the default
            GO Intent value.
        """
        return await self.send_command("P2P_CONNECT", timeout)

    async def send_command_p2p_listen(self, timeout: float = 1) -> bytes:
        """Send message: P2P_LISTEN

        Start Listen-only state. Optional parameter can be used to specify the
            duration for the Listen operation in seconds. This command may
            not be of that much use during normal operations and is mainly
            designed for testing. It can also be used to keep the device discoverable
            without having to maintain a group.
        """
        return await self.send_command("P2P_LISTEN", timeout)

    async def send_command_p2p_group_remove(self, timeout: float = 1) -> bytes:
        """Send message: P2P_GROUP_REMOVE

        Terminate a P2P group. If a new virtual network interface was used for
            the group, it will also be removed. The network interface name
            of the group interface is used as a parameter for this command.

        """
        return await self.send_command("P2P_GROUP_REMOVE", timeout)

    async def send_command_p2p_group_add(self, timeout: float = 1) -> bytes:
        """Send message: P2P_GROUP_ADD

        Set up a P2P group owner manually (i.e., without group owner negotiation
            with a specific peer). This is also known as autonomous GO. Optional
            persistent=<network id>=""> can be used to specify restart of a
            persistent group.
        """
        return await self.send_command("P2P_GROUP_ADD", timeout)

    async def send_command_p2p_prov_disc(self, timeout: float = 1) -> bytes:
        """Send message: P2P_PROV_DISC

        Send P2P provision discovery request to the specified peer. The parameters
            for this command are the P2P device address of the peer and the
            desired configuration method. For example, "P2P_PROV_DISC 02:01:02:03:04:05
            display" would request the peer to display a PIN for us and "P2P_PROV_DISC
            02:01:02:03:04:05 keypad" would request the peer to enter a PIN
            that we display.
        """
        return await self.send_command("P2P_PROV_DISC", timeout)

    async def send_command_p2p_get_passphrase(self, timeout: float = 1) -> bytes:
        """Send message: P2P_GET_PASSPHRASE

        Get the passphrase for a group (only available when acting as a GO).
        """
        return await self.send_command("P2P_GET_PASSPHRASE", timeout)

    async def send_command_p2p_serv_disc_req(self, timeout: float = 1) -> bytes:
        """Send message: P2P-SERV-DISC-REQ"""
        return await self.send_command("P2P-SERV-DISC-REQ", timeout)

    async def send_command_p2p_serv_disc_cancel_req(self, timeout: float = 1) -> bytes:
        """Send message: P2P_SERV_DISC_CANCEL_REQ

        Cancel a pending P2P service discovery request. This command takes a single
            parameter: identifier for the pending query (the value returned
            by  <a class="el" href="ctrl_iface_page.html#ctrl_iface_P2P_SERV_DISC_REQ">P2P_SERV_DISC_REQ</a>
            ), e.g., "P2P_SERV_DISC_CANCEL_REQ 1f77628".
        """
        return await self.send_command("P2P_SERV_DISC_CANCEL_REQ", timeout)

    async def send_command_p2p_serv_disc_resp(self, timeout: float = 1) -> bytes:
        """Send message: P2P-SERV-DISC-RESP"""
        return await self.send_command("P2P-SERV-DISC-RESP", timeout)

    async def send_command_p2p_service_update(self, timeout: float = 1) -> bytes:
        """Send message: P2P_SERVICE_UPDATE

        Indicate that local services have changed. This is used to increment the
            P2P service indicator value so that peers know when previously
            cached information may have changed.
        """
        return await self.send_command("P2P_SERVICE_UPDATE", timeout)

    async def send_command_p2p_serv_disc_external(self, timeout: float = 1) -> bytes:
        """Send message: P2P_SERV_DISC_EXTERNAL

        Configure external processing of P2P service requests: 0 (default) = no
            external processing of requests (i.e., internal code will reject
            each request), 1 = external processing of requests (external program
            is responsible for replying to service discovery requests with
            <a class="el" href="ctrl_iface_page.html#ctrl_iface_P2P_SERV_DISC_RESP">P2P_SERV_DISC_RESP</a>
            ).
        """
        return await self.send_command("P2P_SERV_DISC_EXTERNAL", timeout)

    async def send_command_p2p_reject(self, timeout: float = 1) -> bytes:
        """Send message: P2P_REJECT

        Reject connection attempt from a peer (specified with a device address).
            This is a mechanism to reject a pending GO Negotiation with a peer
            and request to automatically block any further connection or discovery
            of the peer.
        """
        return await self.send_command("P2P_REJECT", timeout)

    async def send_command_p2p_invite(self, timeout: float = 1) -> bytes:
        """Send message: P2P_INVITE

        Invite a peer to join a group or to (re)start a persistent group.
        """
        return await self.send_command("P2P_INVITE", timeout)

    async def send_command_p2p_peer(self, timeout: float = 1) -> bytes:
        """Send message: P2P_PEER

        Fetch information about a discovered peer. This command takes in an argument
            specifying which peer to select: P2P Device Address of the peer,
            "FIRST" to indicate the first peer in the list, or "NEXT-<P2P Device
            Address>" to indicate the entry following the specified peer (to
            allow for iterating through the list).
        """
        return await self.send_command("P2P_PEER", timeout)

    async def send_command_p2p_ext_listen(self, timeout: float = 1) -> bytes:
        """Send message: P2P_EXT_LISTEN

        And a matching reply from the GUI:
        """
        return await self.send_command("P2P_EXT_LISTEN", timeout)

    async def send_command_get_capability(self, option: str, strict: str = "", timeout: float = 1) -> bytes:
        """Send message: GET_CAPABILITY

        Example request/reply pairs:
        """
        return await self.send_command(f"GET_CAPABILITY {option} {strict}", timeout)

    async def send_command_ap_scan(self, ap_scan_value: str, timeout: float = 1) -> bytes:
        """Send message: AP_SCAN

        Change ap_scan value: 0 = no scanning, 1 = wpa_supplicant requests scans
            and uses scan results to select the AP, 2 = wpa_supplicant does
            not use scanning and just requests driver to associate and take
            care of AP selection
        """
        return await self.send_command(f"AP_SCAN {ap_scan_value}", timeout)

    async def send_command_interfaces(self, timeout: float = 1) -> bytes:
        """Send message: INTERFACES

        Following subsections describe the most common event notifications generated
            by wpa_supplicant.
        """
        return await self.send_command("INTERFACES", timeout)

    async def send_command_ctrl_req_(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-REQ-

        WPA_CTRL_REQ: Request information from a user.
        """
        return await self.send_command("CTRL-REQ-", timeout)

    async def send_command_ctrl_event_connected(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-CONNECTED

        WPA_EVENT_CONNECTED: Indicate successfully completed authentication and
            that the data connection is now enabled.
        """
        return await self.send_command("CTRL-EVENT-CONNECTED", timeout)

    async def send_command_ctrl_event_disconnected(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-DISCONNECTED

        WPA_EVENT_DISCONNECTED: Disconnected, data connection is not available

        """
        return await self.send_command("CTRL-EVENT-DISCONNECTED", timeout)

    async def send_command_ctrl_event_terminating(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-TERMINATING

        WPA_EVENT_TERMINATING: wpa_supplicant is exiting
        """
        return await self.send_command("CTRL-EVENT-TERMINATING", timeout)

    async def send_command_ctrl_event_password_changed(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-PASSWORD-CHANGED

        WPA_EVENT_PASSWORD_CHANGED: Password change was completed successfully

        """
        return await self.send_command("CTRL-EVENT-PASSWORD-CHANGED", timeout)

    async def send_command_ctrl_event_eap_notification(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-EAP-NOTIFICATION

        WPA_EVENT_EAP_NOTIFICATION: EAP-Request/Notification received
        """
        return await self.send_command("CTRL-EVENT-EAP-NOTIFICATION", timeout)

    async def send_command_ctrl_event_eap_started(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-EAP-STARTED

        WPA_EVENT_EAP_STARTED: EAP authentication started (EAP-Request/Identity
            received)
        """
        return await self.send_command("CTRL-EVENT-EAP-STARTED", timeout)

    async def send_command_ctrl_event_eap_method(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-EAP-METHOD

        WPA_EVENT_EAP_METHOD: EAP method selected
        """
        return await self.send_command("CTRL-EVENT-EAP-METHOD", timeout)

    async def send_command_ctrl_event_eap_success(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-EAP-SUCCESS

        WPA_EVENT_EAP_SUCCESS: EAP authentication completed successfully
        """
        return await self.send_command("CTRL-EVENT-EAP-SUCCESS", timeout)

    async def send_command_ctrl_event_eap_failure(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-EAP-FAILURE

        WPA_EVENT_EAP_FAILURE: EAP authentication failed (EAP-Failure received)

        """
        return await self.send_command("CTRL-EVENT-EAP-FAILURE", timeout)

    async def send_command_ctrl_event_scan_results(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-SCAN-RESULTS

        WPA_EVENT_SCAN_RESULTS: New scan results available
        """
        return await self.send_command("CTRL-EVENT-SCAN-RESULTS", timeout)

    async def send_command_ctrl_event_bss_added(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-BSS-ADDED

        WPA_EVENT_BSS_ADDED: A new BSS entry was added. The event prefix is followed
            by the BSS entry id and BSSID.
        """
        return await self.send_command("CTRL-EVENT-BSS-ADDED", timeout)

    async def send_command_ctrl_event_bss_removed(self, timeout: float = 1) -> bytes:
        """Send message: CTRL-EVENT-BSS-REMOVED

        WPA_EVENT_BSS_REMOVED: A BSS entry was removed. The event prefix is followed
            by BSS entry id and BSSID.
        """
        return await self.send_command("CTRL-EVENT-BSS-REMOVED", timeout)

    async def send_command_wps_overlap_detected(self, timeout: float = 1) -> bytes:
        """Send message: WPS-OVERLAP-DETECTED

        WPS_EVENT_OVERLAP: WPS overlap detected in PBC mode
        """
        return await self.send_command("WPS-OVERLAP-DETECTED", timeout)

    async def send_command_wps_ap_available_pbc(self, timeout: float = 1) -> bytes:
        """Send message: WPS-AP-AVAILABLE-PBC

        WPS_EVENT_AP_AVAILABLE_PBC: Available WPS AP with active PBC found in scan
            results.
        """
        return await self.send_command("WPS-AP-AVAILABLE-PBC", timeout)

    async def send_command_wps_ap_available_pin(self, timeout: float = 1) -> bytes:
        """Send message: WPS-AP-AVAILABLE-PIN

        WPS_EVENT_AP_AVAILABLE_PIN: Available WPS AP with recently selected PIN
            registrar found in scan results.
        """
        return await self.send_command("WPS-AP-AVAILABLE-PIN", timeout)

    async def send_command_wps_ap_available(self, timeout: float = 1) -> bytes:
        """Send message: WPS-AP-AVAILABLE

        WPS_EVENT_AP_AVAILABLE: Available WPS AP found in scan results
        """
        return await self.send_command("WPS-AP-AVAILABLE", timeout)

    async def send_command_wps_cred_received(self, timeout: float = 1) -> bytes:
        """Send message: WPS-CRED-RECEIVED

        WPS_EVENT_CRED_RECEIVED: A new credential received
        """
        return await self.send_command("WPS-CRED-RECEIVED", timeout)

    async def send_command_wps_m2d(self, timeout: float = 1) -> bytes:
        """Send message: WPS-M2D

        WPS_EVENT_M2D: M2D received
        """
        return await self.send_command("WPS-M2D", timeout)

    async def send_command_ctrl_iface_event_wps_fail(self, timeout: float = 1) -> bytes:
        """Send message: ctrl_iface_event_WPS_FAIL

        WPS_EVENT_FAIL: WPS registration failed after M2/M2D
        """
        return await self.send_command("ctrl_iface_event_WPS_FAIL", timeout)

    async def send_command_wps_success(self, timeout: float = 1) -> bytes:
        """Send message: WPS-SUCCESS

        WPS_EVENT_SUCCESS: WPS registration completed successfully
        """
        return await self.send_command("WPS-SUCCESS", timeout)

    async def send_command_wps_timeout(self, timeout: float = 1) -> bytes:
        """Send message: WPS-TIMEOUT

        WPS_EVENT_TIMEOUT: WPS enrollment attempt timed out and was terminated

        """
        return await self.send_command("WPS-TIMEOUT", timeout)

    async def send_command_wps_enrollee_seen(self, timeout: float = 1) -> bytes:
        """Send message: WPS-ENROLLEE-SEEN

        WPS_EVENT_ENROLLEE_SEEN: WPS Enrollee was detected (used in AP mode). The
            event prefix is followed by MAC addr, UUID-E, pri dev type, config
            methods, dev passwd id, request type, [dev name].
        """
        return await self.send_command("WPS-ENROLLEE-SEEN", timeout)

    async def send_command_wps_er_ap_add(self, timeout: float = 1) -> bytes:
        """Send message: WPS-ER-AP-ADD

        WPS_EVENT_ER_AP_ADD: WPS ER discovered an AP
        """
        return await self.send_command("WPS-ER-AP-ADD", timeout)

    async def send_command_wps_er_ap_remove(self, timeout: float = 1) -> bytes:
        """Send message: WPS-ER-AP-REMOVE

        WPS_EVENT_ER_AP_REMOVE: WPS ER removed an AP entry
        """
        return await self.send_command("WPS-ER-AP-REMOVE", timeout)

    async def send_command_wps_er_enrollee_add(self, timeout: float = 1) -> bytes:
        """Send message: WPS-ER-ENROLLEE-ADD

        WPS_EVENT_ER_ENROLLEE_ADD: WPS ER discovered a new Enrollee
        """
        return await self.send_command("WPS-ER-ENROLLEE-ADD", timeout)

    async def send_command_wps_er_enrollee_remove(self, timeout: float = 1) -> bytes:
        """Send message: WPS-ER-ENROLLEE-REMOVE

        WPS_EVENT_ER_ENROLLEE_REMOVE: WPS ER removed an Enrollee entry
        """
        return await self.send_command("WPS-ER-ENROLLEE-REMOVE", timeout)

    async def send_command_wps_pin_needed(self, timeout: float = 1) -> bytes:
        """Send message: WPS-PIN-NEEDED

        WPS_EVENT_PIN_NEEDED: PIN is needed to complete provisioning with an Enrollee.
            This is followed by information about the Enrollee (UUID, MAC address,
            device name, manufacturer, model name, model number, serial number,
            primary device type).
        """
        return await self.send_command("WPS-PIN-NEEDED", timeout)

    async def send_command_wps_new_ap_settings(self, timeout: float = 1) -> bytes:
        """Send message: WPS-NEW-AP-SETTINGS

        WPS_EVENT_NEW_AP_SETTINGS: New AP settings were received
        """
        return await self.send_command("WPS-NEW-AP-SETTINGS", timeout)

    async def send_command_wps_reg_success(self, timeout: float = 1) -> bytes:
        """Send message: WPS-REG-SUCCESS

        WPS_EVENT_REG_SUCCESS: WPS provisioning was completed successfully (AP/Registrar)

        """
        return await self.send_command("WPS-REG-SUCCESS", timeout)

    async def send_command_wps_ap_setup_locked(self, timeout: float = 1) -> bytes:
        """Send message: WPS-AP-SETUP-LOCKED

        WPS_EVENT_AP_SETUP_LOCKED: AP changed into setup locked state due to multiple
            failed configuration attempts using the AP PIN.
        """
        return await self.send_command("WPS-AP-SETUP-LOCKED", timeout)

    async def send_command_ap_sta_connected(self, timeout: float = 1) -> bytes:
        """Send message: AP-STA-CONNECTED

        AP_STA_CONNECTED: A station associated with us (AP mode event). The event
            prefix is followed by the MAC address of the station.
        """
        return await self.send_command("AP-STA-CONNECTED", timeout)

    async def send_command_ap_sta_disconnected(self, timeout: float = 1) -> bytes:
        """Send message: AP-STA-DISCONNECTED

        AP_STA_DISCONNECTED: A station disassociated (AP mode event)
        """
        return await self.send_command("AP-STA-DISCONNECTED", timeout)

    async def send_command_p2p_device_found(self, timeout: float = 1) -> bytes:
        """Send message: P2P-DEVICE-FOUND

        P2P_EVENT_DEVICE_FOUND: Indication of a discovered P2P device with information
            about that device.
        """
        return await self.send_command("P2P-DEVICE-FOUND", timeout)

    async def send_command_p2p_go_neg_request(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GO-NEG-REQUEST

        P2P_EVENT_GO_NEG_REQUEST: A P2P device requested GO negotiation, but we
            were not ready to start the negotiation.
        """
        return await self.send_command("P2P-GO-NEG-REQUEST", timeout)

    async def send_command_p2p_go_neg_success(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GO-NEG-SUCCESS

        P2P_EVENT_GO_NEG_SUCCESS: Indication of successfully complete group owner
            negotiation.
        """
        return await self.send_command("P2P-GO-NEG-SUCCESS", timeout)

    async def send_command_p2p_go_neg_failure(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GO-NEG-FAILURE

        P2P_EVENT_GO_NEG_FAILURE: Indication of failed group owner negotiation.

        """
        return await self.send_command("P2P-GO-NEG-FAILURE", timeout)

    async def send_command_p2p_group_formation_success(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GROUP-FORMATION-SUCCESS

        P2P_EVENT_GROUP_FORMATION_SUCCESS: Indication that P2P group formation
            has been completed successfully.
        """
        return await self.send_command("P2P-GROUP-FORMATION-SUCCESS", timeout)

    async def send_command_p2p_group_formation_failure(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GROUP-FORMATION-FAILURE

        P2P_EVENT_GROUP_FORMATION_FAILURE: Indication that P2P group formation
            failed (e.g., due to provisioning failure or timeout).
        """
        return await self.send_command("P2P-GROUP-FORMATION-FAILURE", timeout)

    async def send_command_p2p_group_started(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GROUP-STARTED

        P2P_EVENT_GROUP_STARTED: Indication of a new P2P group having been started.
            Additional parameters: network interface name for the group, role
            (GO/client), SSID. The passphrase used in the group is also indicated
            here if known (on GO) or PSK (on client). If the group is a persistent
            one, a flag indicating that is included.
        """
        return await self.send_command("P2P-GROUP-STARTED", timeout)

    async def send_command_p2p_group_removed(self, timeout: float = 1) -> bytes:
        """Send message: P2P-GROUP-REMOVED

        P2P_EVENT_GROUP_REMOVED: Indication of a P2P group having been removed.
            Additional parameters: network interface name for the group, role
            (GO/client).
        """
        return await self.send_command("P2P-GROUP-REMOVED", timeout)

    async def send_command_p2p_prov_disc_show_pin(self, timeout: float = 1) -> bytes:
        """Send message: P2P-PROV-DISC-SHOW-PIN

        P2P_EVENT_PROV_DISC_SHOW_PIN: Request from the peer for us to display a
            PIN that will be entered on the peer. The following parameters
            are included after the event prefix: peer_address PIN. The PIN
            is a random PIN generated for this connection. P2P_CONNECT command
            can be used to accept the request with the same PIN configured
            for the connection.
        """
        return await self.send_command("P2P-PROV-DISC-SHOW-PIN", timeout)

    async def send_command_p2p_prov_disc_enter_pin(self, timeout: float = 1) -> bytes:
        """Send message: P2P-PROV-DISC-ENTER-PIN

        P2P_EVENT_PROV_DISC_ENTER_PIN: Request from the peer for us to enter a
            PIN displayed on the peer. The following parameter is included
            after the event prefix: peer address.
        """
        return await self.send_command("P2P-PROV-DISC-ENTER-PIN", timeout)

    async def send_command_p2p_prov_disc_pbc_req(self, timeout: float = 1) -> bytes:
        """Send message: P2P-PROV-DISC-PBC-REQ

        P2P_EVENT_PROV_DISC_PBC_REQ: Request from the peer for us to connect using
            PBC. The following parameters are included after the event prefix:
            peer_address. P2P_CONNECT command can be used to accept the request.

        """
        return await self.send_command("P2P-PROV-DISC-PBC-REQ", timeout)

    async def send_command_p2p_prov_disc_pbc_resp(self, timeout: float = 1) -> bytes:
        """Send message: P2P-PROV-DISC-PBC-RESP

        P2P-SERV-DISC-RESP: Indicate reception of a P2P service discovery response.
            The following parameters are included after the event prefix: source
            address, Service Update Indicator, Service Response TLV(s) as hexdump.

        """
        return await self.send_command("P2P-PROV-DISC-PBC-RESP", timeout)

    async def send_command_p2p_invitation_received(self, timeout: float = 1) -> bytes:
        """Send message: P2P-INVITATION-RECEIVED

        P2P-INVITATION-RECEIVED: Indicate reception of a P2P Invitation Request.
            For persistent groups, the parameter after the event prefix indicates
            which network block includes the persistent group data.
        """
        return await self.send_command("P2P-INVITATION-RECEIVED", timeout)

    async def send_command_p2p_invitation_result(self, timeout: float = 1) -> bytes:
        """Send message: P2P-INVITATION-RESULT

        shows the status code returned by the peer (or -1 on local failure or timeout).

        """
        return await self.send_command("P2P-INVITATION-RESULT", timeout)


async def main() -> None:
    wpa = WPASupplicant()
    wpa.run(("localhost", 6664))
    time.sleep(1)
    await wpa.send_command_list_networks()
    for i in range(5):
        await wpa.send_command_remove_network(i)

    await wpa.send_command_add_network()
    await wpa.send_command_set_network(0, "ssid", '"wifi_ssid"')
    await wpa.send_command_set_network(0, "psk", '"wifi_password"')
    await wpa.send_command_enable_network(0)
    await wpa.send_command_save_config()
    await wpa.send_command_reconfigure()
    while True:
        time.sleep(1)
        await wpa.send_command_ping()


if __name__ == "__main__":
    asyncio.run(main())
