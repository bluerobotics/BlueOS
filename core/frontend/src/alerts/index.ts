import alert_engine from './engine'
import autopilot from './rules/autopilot'
import backend from './rules/backend'
import network from './rules/network'

alert_engine.register([...backend, ...autopilot, ...network])

export default alert_engine