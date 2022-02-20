export default async function externalComponent(url: string): Promise<HTMLScriptElement> {
  const strings = url.split('/').reverse()[0]
  const matches = strings.match(/^(.*?)\.umd/)?.reverse()[0]
  const name: string = matches || ''

  const typedWindow = window as { [key: string]: any }

  if (typedWindow[name]) return typedWindow[name]

  typedWindow[name] = new Promise((resolve, reject) => {
    const script: HTMLScriptElement = document.createElement('script')
    script.async = true
    script.addEventListener('load', () => {
      resolve(typedWindow[name])
    })
    script.addEventListener('error', () => {
      reject(new Error(`Error loading ${url}`))
    })
    script.src = url
    document.head.appendChild(script)
  })

  return typedWindow[name]
}
