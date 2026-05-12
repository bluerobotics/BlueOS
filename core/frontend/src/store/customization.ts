import {
  Action, getModule,
  Module, Mutation, VuexModule,
} from 'vuex-module-decorators'

import Notifier from '@/libs/notifier'
import store from '@/store'
import { BrandingAsset, ModelEntry, ThemeStatus } from '@/types/customization'
import { customization_service } from '@/types/frontend_services'
import back_axios from '@/utils/api'

const API_URL = '/customization/v1.0'
const notifier = new Notifier(customization_service)
const THEME_CSS_HREF_FRAGMENT = '/userdata/styles/theme_style.css'
const EMPTY_BRANDING: BrandingAsset = { url: null, size_bytes: null }

function reloadThemeCss(): void {
  // Force the browser to re-fetch the generated stylesheet so the new
  // gradient/scrollbar colors take effect immediately.
  const links = document.querySelectorAll('link[rel="stylesheet"]')
  links.forEach((link) => {
    const href = link.getAttribute('href') ?? ''
    if (href.includes(THEME_CSS_HREF_FRAGMENT)) {
      const url = href.split('?')[0]
      link.setAttribute('href', `${url}?t=${Date.now()}`)
    }
  })
}

@Module({ dynamic: true, store, name: 'customization' })
class CustomizationStore extends VuexModule {
  themeStatus: ThemeStatus | null = null

  models: ModelEntry[] = []

  logo: BrandingAsset = { ...EMPTY_BRANDING }

  vehicleImage: BrandingAsset = { ...EMPTY_BRANDING }

  themeSaving = false

  themeResetting = false

  modelUploading = false

  logoUploading = false

  vehicleImageUploading = false

  // Cache-buster for branding URLs. Bumped automatically by setLogo/
  // setVehicleImage so any update to a branding asset yields a new URL.
  brandingVersion = Date.now()

  get logoUrl(): string | null {
    if (!this.logo.url) return null
    return `${this.logo.url}?v=${this.brandingVersion}`
  }

  get vehicleImageUrl(): string | null {
    if (!this.vehicleImage.url) return null
    return `${this.vehicleImage.url}?v=${this.brandingVersion}`
  }

  @Mutation
  setThemeStatus(value: ThemeStatus | null): void {
    this.themeStatus = value
  }

  @Mutation
  setModels(value: ModelEntry[]): void {
    this.models = value
  }

  @Mutation
  setLogo(value: BrandingAsset): void {
    this.logo = value
    this.brandingVersion = Date.now()
  }

  @Mutation
  setVehicleImage(value: BrandingAsset): void {
    this.vehicleImage = value
    this.brandingVersion = Date.now()
  }

  @Mutation
  setThemeSaving(value: boolean): void {
    this.themeSaving = value
  }

  @Mutation
  setThemeResetting(value: boolean): void {
    this.themeResetting = value
  }

  @Mutation
  setModelUploading(value: boolean): void {
    this.modelUploading = value
  }

  @Mutation
  setLogoUploading(value: boolean): void {
    this.logoUploading = value
  }

  @Mutation
  setVehicleImageUploading(value: boolean): void {
    this.vehicleImageUploading = value
  }

  @Action
  async refreshAll(): Promise<void> {
    await Promise.all([
      this.fetchTheme(),
      this.fetchModels(),
      this.fetchLogo(),
      this.fetchVehicleImage(),
    ])
  }

  @Action
  async fetchTheme(): Promise<void> {
    try {
      const response = await back_axios({ method: 'get', url: `${API_URL}/theme`, timeout: 10000 })
      this.setThemeStatus(response.data)
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_GET_THEME', error)
    }
  }

  @Action
  async saveTheme(primary: string): Promise<void> {
    this.setThemeSaving(true)
    try {
      const response = await back_axios({
        method: 'put',
        url: `${API_URL}/theme`,
        data: { primary },
        timeout: 10000,
      })
      this.setThemeStatus(response.data)
      reloadThemeCss()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_SAVE_THEME', error)
    } finally {
      this.setThemeSaving(false)
    }
  }

  @Action
  async resetTheme(): Promise<void> {
    this.setThemeResetting(true)
    try {
      await back_axios({ method: 'delete', url: `${API_URL}/theme`, timeout: 10000 })
      await this.fetchTheme()
      reloadThemeCss()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_RESET_THEME', error)
    } finally {
      this.setThemeResetting(false)
    }
  }

  @Action
  async fetchModels(): Promise<void> {
    try {
      const response = await back_axios({ method: 'get', url: `${API_URL}/models`, timeout: 10000 })
      this.setModels(response.data ?? [])
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_LIST_MODELS', error)
    }
  }

  @Action
  async uploadModel({ file, name }: { file: File; name: string }): Promise<void> {
    const form_data = new FormData()
    form_data.append('file', file)
    this.setModelUploading(true)
    try {
      await back_axios({
        method: 'post',
        url: `${API_URL}/models`,
        params: { name },
        headers: { 'Content-Type': 'multipart/form-data' },
        data: form_data,
        timeout: 120000,
      })
      await this.fetchModels()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_UPLOAD_MODEL', error)
    } finally {
      this.setModelUploading(false)
    }
  }

  @Action
  async deleteModel(name: string): Promise<void> {
    // Backend route uses `{name:path}` so `/` must remain literal
    const encoded_name = name.split('/').map(encodeURIComponent).join('/')
    try {
      await back_axios({
        method: 'delete',
        url: `${API_URL}/models/${encoded_name}`,
        timeout: 10000,
      })
      await this.fetchModels()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_DELETE_MODEL', error)
    }
  }

  @Action
  async fetchLogo(): Promise<void> {
    try {
      const response = await back_axios({ method: 'get', url: `${API_URL}/branding/logo`, timeout: 10000 })
      this.setLogo(response.data)
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_GET_LOGO', error)
    }
  }

  @Action
  async uploadLogo(file: File): Promise<void> {
    const form_data = new FormData()
    form_data.append('file', file)
    this.setLogoUploading(true)
    try {
      await back_axios({
        method: 'post',
        url: `${API_URL}/branding/logo`,
        headers: { 'Content-Type': 'multipart/form-data' },
        data: form_data,
        timeout: 60000,
      })
      await this.fetchLogo()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_UPLOAD_LOGO', error)
    } finally {
      this.setLogoUploading(false)
    }
  }

  @Action
  async deleteLogo(): Promise<void> {
    try {
      await back_axios({ method: 'delete', url: `${API_URL}/branding/logo`, timeout: 10000 })
      await this.fetchLogo()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_DELETE_LOGO', error)
    }
  }

  @Action
  async fetchVehicleImage(): Promise<void> {
    try {
      const response = await back_axios({
        method: 'get',
        url: `${API_URL}/branding/vehicle-image`,
        timeout: 10000,
      })
      this.setVehicleImage(response.data)
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_GET_VEHICLE_IMAGE', error)
    }
  }

  @Action
  async uploadVehicleImage(file: File): Promise<void> {
    const form_data = new FormData()
    form_data.append('file', file)
    this.setVehicleImageUploading(true)
    try {
      await back_axios({
        method: 'post',
        url: `${API_URL}/branding/vehicle-image`,
        headers: { 'Content-Type': 'multipart/form-data' },
        data: form_data,
        timeout: 60000,
      })
      await this.fetchVehicleImage()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_UPLOAD_VEHICLE_IMAGE', error)
    } finally {
      this.setVehicleImageUploading(false)
    }
  }

  @Action
  async deleteVehicleImage(): Promise<void> {
    try {
      await back_axios({
        method: 'delete',
        url: `${API_URL}/branding/vehicle-image`,
        timeout: 10000,
      })
      await this.fetchVehicleImage()
    } catch (error) {
      notifier.pushBackError('CUSTOMIZATION_DELETE_VEHICLE_IMAGE', error)
    }
  }
}

const customization_store = getModule(CustomizationStore)

export { CustomizationStore }
export default customization_store
