/** Represents a Companion service, with the necessary information to identify it on the system */
export interface Service {
  name: string
  description: string
  icon?: URL
  company: string
  version: string
  webpage?: URL
  api?: URL
  webapp?: {
      service_page?: URL
  }
}
