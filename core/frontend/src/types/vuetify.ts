export type VForm = Vue & {
    reset: () => void,
    resetValidation: () => void,
    validate: () => boolean,
}
