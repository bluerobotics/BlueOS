<template>
  <v-container fluid>
    <v-row>
      <v-col>
        <v-card>
          <v-card-title>
            Zenoh Network
            <v-spacer />
            <v-btn
              icon
              :loading="loading"
              @click="refreshNetwork"
            >
              <v-icon>mdi-refresh</v-icon>
            </v-btn>
          </v-card-title>
          <v-card-text class="pb-0">
            <v-row class="legend-container">
              <v-col cols="12">
                <div class="legend-title">
                  Node Types:
                </div>
                <div class="legend-items">
                  <div class="legend-item">
                    <div class="legend-color client" />
                    <span>Client ({{ getNodeCount('client') }})</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color router" />
                    <span>Router ({{ getNodeCount('router') }})</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color peer" />
                    <span>Peer ({{ getNodeCount('peer') }})</span>
                  </div>
                  <div class="legend-item">
                    <div class="legend-color error" />
                    <span>Error ({{ getNodeCount('error') }})</span>
                  </div>
                </div>
              </v-col>
            </v-row>
          </v-card-text>

          <v-card-text>
            <div
              id="cy"
              ref="cyContainer"
              style="width: 100%; height: 600px; border: 1px solid #ccc;"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script lang="ts">
import {
  ChannelReceiver, Config, QueryTarget, Reply, ReplyError,
  Sample, Session,
} from '@eclipse-zenoh/zenoh-ts'
import cytoscape, { Core, StylesheetJsonBlock } from 'cytoscape'
import fcose, { FcoseLayoutOptions } from 'cytoscape-fcose'
import Vue from 'vue'

interface NetworkNode {
  id: string
  whatami: string
  name?: string
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  metadata?: any
}

interface NetworkEdge {
  source: string
  target: string
  protocol: string
}

export default Vue.extend({
  name: 'ZenohNetwork',
  data() {
    return {
      session: null as Session | null,
      cy: null as Core | null,
      loading: false,
      networkData: {
        nodes: [] as NetworkNode[],
        edges: [] as NetworkEdge[],
      },
    }
  },
  async mounted() {
    await this.setupZenoh()
    this.$nextTick(() => {
      this.initCytoscape()
    })
  },
  beforeDestroy() {
    this.disconnectZenoh()
  },
  methods: {
    initCytoscape() {
      try {
        const container = this.$refs.cyContainer as HTMLElement
        if (!container) {
          console.error('[Zenoh Network] Container not found')
          return
        }

        // Prepare elements for Cytoscape
        const elements = this.prepareCytoscapeElements()
        cytoscape.use(fcose)

        this.cy = cytoscape({
          container,
          boxSelectionEnabled: false,
          elements,
          layout: {
            name: 'fcose',
            animationDuration: 1500,
            fit: true,
            tile: true,
            idealEdgeLength: 140,
            packComponents: false,
            nodeRepulsion: 25000,
          } as FcoseLayoutOptions,
          style: this.getCytoscapeStyle(),
        })

        console.log('[Zenoh Network] Cytoscape initialized successfully')
      } catch (error) {
        console.error('[Zenoh Network] Cytoscape initialization error:', error)
      }
    },

    prepareCytoscapeElements(): cytoscape.ElementDefinition[] {
      const elements: cytoscape.ElementDefinition[] = []

      // Add nodes
      this.networkData.nodes.forEach((node) => {
        elements.push({
          data: {
            id: node.id,
            whatami: node.whatami,
            name: node.name,
            metadata: node.metadata,
            label: node.name || node.id,
          },
        })
      })

      // Add edges
      this.networkData.edges.forEach((edge, index) => {
        elements.push({
          data: {
            id: `edge-${index}`,
            source: edge.source,
            target: edge.target,
            protocol: edge.protocol,
          },
        })
      })

      return elements
    },

    getCytoscapeStyle(): StylesheetJsonBlock[] {
      return [
        {
          selector: 'node',
          style: {
            'background-color': '#666',
            label: 'data(label)', // Use the label field which contains name or id
            'text-valign': 'center',
            'text-halign': 'center',
            color: '#fff',
            'font-size': '12px',
            'font-weight': 'bold',
            'text-outline-width': 2,
            'text-outline-color': '#000',
          },
        },
        // Remember to update the css if the colors here change
        {
          selector: 'node[whatami = "client"]',
          style: {
            'background-color': '#4CAF50', // green
            width: 45,
            height: 45,
          },
        },
        {
          selector: 'node[whatami = "router"]',
          style: {
            'background-color': '#4682B4', // steelblue
            width: 50,
            height: 50,
          },
        },
        {
          selector: 'node[whatami = "peer"]',
          style: {
            'background-color': '#FFD700', // yellow
            width: 40,
            height: 40,
          },
        },
        {
          selector: 'node[whatami = "error"]',
          style: {
            'background-color': '#FF8C00', // orange
            width: 40,
            height: 40,
          },
        },
        {
          selector: 'edge',
          style: {
            width: 3,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(protocol)',
            'font-size': '10px',
            'text-rotation': 'autorotate',
          },
        },
      ]
    },
    updateCytoscapeGraph() {
      if (!this.cy) {
        console.warn('[Zenoh Network] Cytoscape not initialized')
        return
      }

      try {
        this.cy.elements().remove()

        const elements = this.prepareCytoscapeElements()
        this.cy.add(elements)

        this.cy.layout({
          name: 'fcose',
          animationDuration: 1500,
          fit: true,
          tile: true,
          idealEdgeLength: 140,
          packComponents: false,
          nodeRepulsion: 25000,
        } as FcoseLayoutOptions).run()
      } catch (error) {
        console.error('[Zenoh Network] Graph update error:', error)
      }
    },

    async setupZenoh() {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const url = `${protocol}://${window.location.host}/zenoh-api/`
        const config = new Config(url)
        this.session = await Session.open(config)

        await this.discoverNetworkTopology()
      } catch (innerError: unknown) {
        const error = innerError as Error
        console.error('[Zenoh Network] Setup error:', error)
        console.error('[Zenoh Network] Error details:', {
          message: error.message,
          stack: error.stack,
          name: error.name,
        })

        // Add a fallback node to show something
        this.networkData.nodes.push({
          id: 'error-node',
          whatami: 'error',
        })
      }
    },

    async discoverNetworkTopology() {
      try {
        await this.queryRouters()
        await this.queryPeers()

        // Query specific nodes for detailed information
        await this.queryAllSpecificNodes()
      } catch (error) {
        console.error('[Zenoh Network] Network discovery error:', error)
      }
    },
    async queryRouters() {
      try {
        const receiver: ChannelReceiver<Reply> | undefined = await this.session!.get('@/*/router', {
          target: QueryTarget.BEST_MATCHING,
        })

        if (!receiver) {
          console.warn('[Zenoh Network] Router query returned void')
          return
        }

        let responseCount = 0
        for await (const reply of receiver) {
          if (responseCount >= 10) break

          const resp = reply.result()
          if (resp instanceof Sample) {
            const sample: Sample = resp
            responseCount += 1

            try {
              const payload = sample.payload().toString()
              console.debug('[Zenoh Network] Router payload:', payload)

              const data = JSON.parse(payload)

              // Add router node
              const zid = data.zid || 'unknown-router'
              const metadata = data.metadata || {}
              this.networkData.nodes.push({
                id: zid,
                whatami: 'router',
                metadata,
              })

              // Add connected sessions
              if (data.sessions && Array.isArray(data.sessions)) {
                for (const sess of data.sessions) {
                  const peer = sess.peer || 'unknown-peer'
                  const whatami = sess.whatami || 'unknown'

                  let linkProtocols = 'unknown'
                  try {
                    if (sess.links && Array.isArray(sess.links)) {
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      linkProtocols = sess.links.map((link: any) => {
                        if (typeof link === 'string') {
                          return link.split('/')[0]
                        }
                        return link.src?.split('/')[0] || 'unknown'
                      }).join(',')
                    }
                  } catch (error) {
                    console.warn('Error parsing link protocols:', error)
                  }

                  this.networkData.nodes.push({
                    id: peer,
                    whatami,
                  })

                  this.networkData.edges.push({
                    source: zid,
                    target: peer,
                    protocol: linkProtocols,
                  })
                }
              }
            } catch (parseError) {
              console.error('[Zenoh Network] Error parsing router response:', parseError)
            }
          } else {
            const replyError: ReplyError = resp
            console.error('[Zenoh Network] Router query error:', replyError.payload().toString())
          }
        }
      } catch (error) {
        console.warn('[Zenoh Network] Router query failed:', error)
      }
    },
    async queryPeers() {
      try {
        const receiver: ChannelReceiver<Reply> | undefined = await this.session!.get('@/*/peer', {
          target: QueryTarget.BEST_MATCHING,
        })

        if (!receiver) {
          console.warn('[Zenoh Network] Peer query returned void')
          return
        }

        let responseCount = 0
        for await (const reply of receiver) {
          if (responseCount >= 10) break

          const resp = reply.result()
          if (resp instanceof Sample) {
            const sample: Sample = resp
            responseCount += 1

            try {
              const payload = sample.payload().toString()
              const data = JSON.parse(payload)
              const peerId = data.zid || data.id || 'unknown-peer'
              if (!this.networkData.nodes.find((n) => n.id === peerId)) {
                this.networkData.nodes.push({
                  id: peerId,
                  whatami: 'peer',
                })
              }
            } catch (parseError) {
              console.error('[Zenoh Network] Error parsing peer response:', parseError)
            }
          } else {
            const replyError: ReplyError = resp
            console.error('[Zenoh Network] Peer query error:', replyError.payload().toString())
          }
        }
      } catch (error) {
        console.warn('[Zenoh Network] Peer query failed:', error)
      }
    },

    async querySpecificNode(zid: string, whatami: string) {
      try {
        const keyexpr = `@/${zid}/${whatami}`

        const receiver: ChannelReceiver<Reply> | undefined = await this.session!.get(keyexpr, {
          target: QueryTarget.BEST_MATCHING,
        })

        if (!receiver) {
          console.warn(`[Zenoh Network] Specific node query for ${keyexpr} returned void`)
          return null
        }

        const reply = await receiver.receive()
        const resp = reply.result()
        if (resp instanceof Sample) {
          const sample: Sample = resp
          try {
            const payload = sample.payload().toString()
            console.debug(`[Zenoh Network] Specific node response for ${keyexpr}:`, payload)
            const data = JSON.parse(payload)

            if (whatami === 'peer' && Array.isArray(data.sessions)) {
              this.processPeerConnections(zid, data.sessions)
            }

            return data
          } catch (parseError) {
            console.error(`[Zenoh Network] Error parsing specific node response for ${keyexpr}:`, parseError)
            return null
          }
        }

        const replyError: ReplyError = resp
        console.error(`[Zenoh Network] Specific node query error for ${keyexpr}:`, replyError.payload().toString())
        return null
      } catch (error) {
        console.warn(`[Zenoh Network] Specific node query failed for ${zid}/${whatami}:`, error)
        return null
      }
    },
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    processPeerConnections(peerZid: string, sessions: any[]) {
      try {
        for (const session of sessions) {
          const peer = session.peer || 'unknown-peer'
          const whatami = session.whatami || 'unknown'

          // Add the connected peer if it doesn't exist
          if (!this.networkData.nodes.find((n) => n.id === peer)) {
            this.networkData.nodes.push({
              id: peer,
              whatami,
            })
          }

          // Extract protocol information from links
          let linkProtocols = 'unknown'
          try {
            if (session.links && Array.isArray(session.links)) {
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              linkProtocols = session.links.map((link: any) => {
                if (typeof link === 'string') {
                  return link.split('/')[0]
                }
                return link.src?.split('/')[0] || 'unknown'
              }).join(',')
            }
          } catch (error) {
            console.warn('Error parsing peer link protocols:', error)
          }

          // Add edge from this peer to the connected items
          // Check if edge already exists to avoid duplicates
          const existingEdge = this.networkData.edges.find(
            (e) => e.source === peerZid && e.target === peer || e.source === peer && e.target === peerZid,
          )

          if (!existingEdge) {
            this.networkData.edges.push({
              source: peerZid,
              target: peer,
              protocol: linkProtocols,
            })
          }
        }
      } catch (error) {
        console.error('[Zenoh Network] Error processing peer connections:', error)
      }
    },
    async queryAllSpecificNodes() {
      try {
        for (const node of this.networkData.nodes) {
          if (node.whatami && node.whatami !== 'unknown') {
            const detailedInfo = await this.querySpecificNode(node.id, node.whatami)
            if (detailedInfo) {
              // Update the node with detailed information
              node.metadata = { ...node.metadata, ...detailedInfo }

              if (detailedInfo.metadata?.name) {
                node.name = detailedInfo.metadata.name
                console.debug(`[Zenoh Network] Updated node ${node.id} with name: ${detailedInfo.metadata.name}`)
              }
            }
          }
        }

        console.debug('[Zenoh Network] Specific node queries completed')

        // Update the graph to show the new names
        this.updateCytoscapeGraph()
      } catch (error) {
        console.warn('[Zenoh Network] Error querying specific nodes:', error)
      }
    },

    async refreshNetwork() {
      this.loading = true
      try {
        // Clear the Cytoscape graph first
        if (this.cy) {
          this.cy.elements().remove()
          console.log('[Zenoh Network] Cleared Cytoscape graph')
        }

        // Clear all existing data
        this.networkData.nodes = []
        this.networkData.edges = []

        // Close existing session and create a new one
        if (this.session) {
          await this.session.close()
          this.session = null
        }

        // Setup new Zenoh connection
        await this.setupZenoh()

        // Ensure Cytoscape is initialized and update the graph
        if (!this.cy) {
          console.log('[Zenoh Network] Cytoscape not initialized, initializing now...')
          this.$nextTick(() => {
            this.initCytoscape()
          })
        } else {
          this.updateCytoscapeGraph()
        }
      } finally {
        this.loading = false
      }
    },

    async disconnectZenoh() {
      if (this.session) {
        await this.session.close()
        this.session = null
      }
    },

    getNodeCount(whatami: string) {
      return this.networkData.nodes.filter((node) => node.whatami === whatami).length
    },
  },
})
</script>

<style scoped>
.network-info {
  margin-bottom: 20px;
  padding: 10px;
  background-color: #f5f5f5;
  border-radius: 4px;
}

.network-info p {
  margin: 5px 0;
  font-weight: bold;
}

.legend-container {
  margin-bottom: 10px;
}

.legend-title {
  font-weight: bold;
  margin-bottom: 5px;
}

.legend-items {
  display: flex;
  gap: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-color {
  width: 20px;
  height: 20px;
  border-radius: 50%;
}

.client {
  background-color: #4CAF50;
}

.router {
  background-color: #4682B4;
}

.peer {
  background-color: #FFD700;
}

.error {
  background-color: #FF8C00;
}
</style>
