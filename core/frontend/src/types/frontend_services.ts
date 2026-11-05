import { t } from 'ttag'

import { Service } from './common'

export const frontend_service: Service = {
  name: t`BlueOS Frontend`,
  description: t`Frontend status and logic.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const service_scanner_service: Service = {
  name: t`Service Scanner`,
  description: t`Actual scanner for running services.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const wifi_service: Service = {
  name: t`Wifi Manager`,
  description: t`Service responsible for managing wifi configuration on BlueOS.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const ethernet_service: Service = {
  name: t`Ethernet Manager`,
  description: t`Responsible for management of ethernet adapters configuration.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const autopilot_service: Service = {
  name: t`Autopilot Manager`,
  description: t`Responsible for management of autopilot status and configuration.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const filebrowser_service: Service = {
  name: t`Filebrowser`,
  description: t`File browsing service.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const video_manager_service: Service = {
  name: t`Video Manager`,
  description: t`Video management service for BlueOS.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const mavlink_service: Service = {
  name: t`MavLink2Rest`,
  description: t`MavLink communication layer over REST API.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const beacon_service: Service = {
  name: t`Beacon`,
  description: t`Publishes mDNS entries and related utilities`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const bridget_service: Service = {
  name: t`Bridget`,
  description: t`Bridges management service for BlueOS.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const commander_service: Service = {
  name: t`Commander`,
  description: t`Helper program to provide easy access to commands via REST API.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const customization_service: Service = {
  name: t`Customization`,
  description: t`Manage BlueOS visual customization (theme color, 3D model overrides, branding).`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const nmea_injector_service: Service = {
  name: t`NMEA Injector`,
  description: t`Allows management of sockets for NMEA data injectior.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const system_information_service: Service = {
  name: t`System Information`,
  description: t`Provides system information, E.g: CPU, disk, network interface and etc.`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const network_speed_test_service: Service = {
  name: t`Network Speed Test`,
  description: t`Service to test network speed`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const update_time_service: Service = {
  name: t`Update time`,
  description: t`Service to update system time`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const ping_service: Service = {
  name: t`Ping service`,
  description: t`Service to manage ping devices`,
  company: 'Blue Robotics',
  version: '0.2.0',
}

export const kraken_service: Service = {
  name: t`Kraken service`,
  description: t`Service to manage BlueOS extensions`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const parameters_service: Service = {
  name: t`Parameters service`,
  description: t`Service to manage vehicle Parameters`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const bag_of_holding_service: Service = {
  name: t`Bag Of Holding`,
  description: t`Service to manage json database for the vehicle`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const helper_service: Service = {
  name: t`Helper service`,
  description: t`Simple helper service for the frontend and simple features`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const version_chooser_service: Service = {
  name: t`Version chooser service`,
  description: t`Manage versions of BlueOS and bootstrap`,
  company: 'Blue Robotics',
  version: '0.1.0',
}

export const pardal_service: Service = {
  name: t`Pardal service`,
  description: t`Service to manage Pardal`,
  company: 'Blue Robotics',
  version: '0.1.0',
}
