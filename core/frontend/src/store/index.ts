import Vue from 'vue'
import Vuex from 'vuex'

Vue.use(Vuex)

const oldSetInterval = window.setInterval
const oldClearInterval = window.clearInterval

window.namedIntervals = {}
window.intervals = []

window.setInterval = (handler: Function, timeout: number) => {
  console.warn("Please Consider using setNamedInterval instead!")
  
  console.trace()
  const interval = oldSetInterval(handler, timeout)
  window.intervals.push(interval)
  console.log('Interval set', interval, handler, timeout)
  return interval
}

window.setNamedInterval = (name: string, handler: Function, timeout: number) => {
  if (window.namedIntervals[name]) {
    console.error('Interval already exists', name)
    return
  }
  const interval = oldSetInterval(handler, timeout)
  window.namedIntervals[name] = interval
  return interval
}

window.clearInterval = (interval: number | string) => {
  if ((typeof interval) === 'string') {
    console.log('Clearing named interval', interval)
    interval = window.namedIntervals[interval]
    if (!interval) {
      console.error('Tried to clear non-existing interval:', interval)
      return
    }
    console.log('Interval cleared', interval)
    oldClearInterval(interval)
    window.namedIntervals = Object.fromEntries(Object.entries(window.namedIntervals).filter(([key, value]) => value !== interval))
    return
  }
  if (!window.intervals.includes(interval)) {
    console.error('Interval not found', interval)
    return
  }
  console.log('Interval cleared', interval)
  oldClearInterval(interval)
  window.intervals = window.intervals.filter((i) => i !== interval)
}

export default new Vuex.Store({})
