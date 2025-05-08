<template>
  <v-container fluid>
    <v-row>
      <v-col
        sm="3"
      >
        <v-sheet
          rounded="lg"
          min-height="268"
        >
          <v-card
            class="mx-auto height-limited"
            max-height="700px"
          >
            <v-text-field
              v-model="message_filter"
              class="ma-2"
              label="Search"
              clearable
              prepend-inner-icon="mdi-magnify"
            />
            <v-list shaped>
              <v-list-item-group
                v-model="selected_message_types"
                multiple
              >
                <template v-for="(item, i) in filtered_messages">
                  <v-list-item
                    :key="i"
                    :value="item"
                    active-class="deep-purple--text text--accent-4"
                  >
                    <template #default="{ active }">
                      <v-list-item-content>
                        <v-list-item-title v-text="item" />
                      </v-list-item-content>

                      <v-list-item-action>
                        <v-checkbox
                          :input-value="active"
                          color="deep-purple accent-4"
                        />
                      </v-list-item-action>
                    </template>
                  </v-list-item>
                </template>
              </v-list-item-group>
            </v-list>
          </v-card>
        </v-sheet>
      </v-col>

      <v-col
        sm="6"
        height="700px"
      >
        <v-sheet
          rounded="lg"
        >
          <v-card>
            <v-virtual-scroll
              :items="messages_in_view"
              :item-height="40"
              height="700px"
            >
              <template #default="{ item }">
                <v-list-item
                  @click="showDetailed(item)"
                >
                  <v-list-item-content>
                    <v-list-item-title>
                      {{ item.timestamp.toLocaleString() }} | {{ item | prettyPrint }}
                    </v-list-item-title>
                  </v-list-item-content>
                </v-list-item>
              </template>
            </v-virtual-scroll>
          </v-card>
        </v-sheet>
      </v-col>

      <v-col
        sm="3"
      >
        <v-card
          v-if="detailed_message"
          outlined
          width="100%"
        >
          <v-card-text
            style="overflow: auto;"
          >
            <pre> {{ detailed_message }} </pre>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>
<script lang="ts">
import Vue from 'vue'

import mavlink2rest from '@/libs/MAVLink2Rest'
import { Message } from '@/libs/MAVLink2Rest/mavlink2rest-ts/messages/mavlink2rest'
import { Dictionary } from '@/types/common'
import prettify from '@/utils/mavlink_prettifier'

import { Config, Session, Queryable, Query, Liveliness, LivelinessToken, Reply, Sample, Receiver, KeyExpr, Subscriber, SampleKind, Publisher } from '@eclipse-zenoh/zenoh-ts'

const KEYEXPR_CHAT_USER = new KeyExpr("**")
const KEYEXPR_CHAT_MESSAGES = new KeyExpr("**")

export class ChatUser {
	username: string;

	constructor(username: string) {
		this.username = username;
	}
	public static fromString(username: string): ChatUser {
		return new ChatUser(username);
	}
	public static fromKeyexpr(keyexpr: KeyExpr): ChatUser | null {
		let keyexpr_str = keyexpr.toString();
		let index = keyexpr_str.lastIndexOf("/");
		if (index == -1) {
			return null;
		}
		let prefix = keyexpr_str.substring(0, index);
		let username = keyexpr_str.substring(index + 1);
		if (prefix != KEYEXPR_CHAT_USER.toString()) {
			return null;
		}
		return new ChatUser(username);
	}
	public toKeyexpr(): KeyExpr {
		return KEYEXPR_CHAT_USER.join(this.username);
	}
	public toString(): string {
		return this.username;
	}
}

export interface ChatMessage {
	t: string; // timestamp
	u: string; // username
	m: string; // message
}

export class ChatSession {
	session: Session | null = null;
	liveliness_token: LivelinessToken | null = null;
	liveliness_subscriber: Subscriber | null = null;
	messages_queryable: Queryable | null = null;
	messages_publisher: Publisher | null = null;
	message_subscriber: Subscriber | null = null;

	usersCallback: (() => void) | null = null;
	messageCallback: ((user: ChatUser, message: string) => void) | null = null;
	onConnectCallback: ((chatSession: ChatSession) => void) | null = null;
	onDisconnectCallback: ((chatSession: ChatSession) => void) | null = null;

	onConnect(callback: (chatSession: ChatSession) => void) {
		this.onConnectCallback = callback;
	}

	onDisconnect(callback: (chatSession: ChatSession) => void) {
		this.onDisconnectCallback = callback;
	}

	onChangeUsers(callback: (chatSession: ChatSession) => void) {
		this.usersCallback = () => callback(this);
	}

	onNewMessage(callback: (chatSession: ChatSession, user: ChatUser, message: string) => void) {
		this.messageCallback = (user, message) => callback(this, user, message);
	}

	user: ChatUser;
	users: ChatUser[] = [];
	messages: ChatMessage[] = [];

	constructor(user: ChatUser) {
		this.user = user;
	}

	public async connect(serverUrl: string): Promise<void> {
		let config = new Config(serverUrl);
		this.session = await Session.open(config);
		log(`[Session] Open ${serverUrl}`);

		let keyexpr = this.user.toKeyexpr();

		let receiver = await this.session.get(KEYEXPR_CHAT_MESSAGES) as Receiver;
		log(`[Session] Get from ${KEYEXPR_CHAT_MESSAGES.toString()}`);
		let reply = await receiver.receive();
		if (reply instanceof Reply) {
			let resp = reply.result();
			if (resp instanceof Sample) {
				let payload = resp.payload().to_string();
				let attachment = resp.attachment()?.to_string() ?? "";
				log(`[Session] GetSuccess from ${resp.keyexpr().toString()}, messages: ${payload}, from user: ${attachment}`);
				this.messages = JSON.parse(payload);
			}
		} else {
			log(`[Session] GetError ${reply}`);
		}

		this.messages_queryable = await this.session.declare_queryable(KEYEXPR_CHAT_MESSAGES, {
			handler: async (query: Query) => {
				log(`[Queryable] Replying to query: ${query.selector().toString()}`);
				const response = JSON.stringify(this.messages);
				query.reply(KEYEXPR_CHAT_MESSAGES, response, {
					attachment: this.user.username
				});
			},
			complete: true
		});
		log(`[Session] Declare queryable on ${keyexpr}`);

		this.messages_publisher = this.session.declare_publisher(keyexpr, {});
		log(`[Session] Declare publisher on ${keyexpr}`);

		this.message_subscriber = await this.session.declare_subscriber(KEYEXPR_CHAT_USER.join("*"),
			{
				handler: (sample: Sample) => {
					let message = sample.payload().to_string();
					log(`[Subscriber] Received message: ${message} from ${sample.keyexpr().toString()}`);
					let user = ChatUser.fromKeyexpr(sample.keyexpr());
					if (user) {
						const timestamp = new Date().toISOString();
						this.messages.push({ t: timestamp, u: user.username, m: message });
						if (this.messageCallback) {
							this.messageCallback(user, message);
						}
					}
					return Promise.resolve();
				}
			}
		);
		log(`[Session] Declare Subscriber on ${KEYEXPR_CHAT_USER.join("*").toString()}`);

		this.liveliness_token = this.session.liveliness().declare_token(keyexpr);
		log(`[Session] Declare liveliness token on ${keyexpr}`);

		// Subscribe to changes of users presence
		this.liveliness_subscriber = this.session.liveliness().declare_subscriber(KEYEXPR_CHAT_USER.join("*"), {
			handler: (sample: Sample) => {
				let keyexpr = sample.keyexpr();
				let user = ChatUser.fromKeyexpr(keyexpr);
				if (!user) {
					log(`Invalid user keyexpr: ${keyexpr.toString()}`);
				} else {
					switch (sample.kind()) {
						case SampleKind.PUT: {
							log(
								`[LivelinessSubscriber] New alive token ${keyexpr}`
							);
							this.users.push(user);
							break;
						}
						case SampleKind.DELETE: {
							log(
								`[LivelinessSubscriber] Dropped token ${keyexpr}`
							);
							this.users = this.users.filter(u => u.username != user?.username);
							break;
						}
					}
				}
				if (this.usersCallback) {
					this.usersCallback();
				}
				return Promise.resolve();
			},
			history: true
		});
		log(`[Session] Declare liveliness subscriber on ${KEYEXPR_CHAT_USER.join("*").toString()}`);

		if (this.onConnectCallback) {
			this.onConnectCallback(this);
		}
	}

	getUser(): ChatUser {
		return this.user;
	}

	getUsers(): ChatUser[] {
		return this.users;
	}

	getMessages(): ChatMessage[] {
		return this.messages;
	}

	async sendMessage(message: string) {
		if (this.messages_publisher) {
			log(`[Publisher] Put message: ${message}`);
			await this.messages_publisher.put(message);
		}
	}

	async disconnect() {
		if (this.session) {
			await this.session.close();
			log(`[Session] Close`);
			this.session = null;
			this.liveliness_token = null;
			this.messages_queryable = null;
			this.liveliness_subscriber = null;
			this.messages_publisher = null;
			this.message_subscriber = null;
			this.users = [];
			this.messages = [];
			if (this.onDisconnectCallback) {
				this.onDisconnectCallback(this);
			}
		}
	}
}

function log(message: string) {
	//const technicalLog = document.getElementById('technical-log') as HTMLDivElement;
	//const timestamp = new Date().toLocaleTimeString();
	//const logMessage = document.createElement('div');
	//logMessage.textContent = `[${timestamp}] ${message}`;
	//technicalLog.appendChild(logMessage);
	//technicalLog.scrollTop = technicalLog.scrollHeight; // Scroll to the latest log message
  console.log(message);
}

const chatSession = new ChatSession(ChatUser.fromString("user1"));
await chatSession.connect("ws://192.168.31.179:10000");

class MAVLinkMessageTable {
  tables: Dictionary<Array<Message>> = {}

  messageTypes: string[] = []

  size_limit = 100 // do not store more than 100 of each message

  constructor() {
    this.tables = {}
  }

  add(mavlink_message: Message): void {
    const message_timed = mavlink_message
    message_timed.timestamp = new Date()
    const { message } = mavlink_message
    if (message.type in this.tables) {
      this.tables[message.type].push(message_timed)
      if (this.tables[message.type].length > this.size_limit) {
        this.tables[message.type].shift()
      }
    } else {
      this.tables[message.type] = [message_timed]
    }
  }

  getTypes(): string[] {
    return Object.keys(this.tables).sort()
  }

  get(types: string[]): Message[] {
    let result: Message[] = []
    for (const type of types) {
      result = [...result, ...this.tables[type]]
    }
    return result.sort((x, y) => x.timestamp - y.timestamp)
  }
}

export default Vue.extend({
  name: 'ZenohInspector',
  components: {
  },
  filters: {
    prettyPrint(mavlink_message: Message) {
      return prettify(mavlink_message.message)
    },
  },
  data() {
    return {
      message_types: [] as string[],
      message_table: new MAVLinkMessageTable(),
      message_type_interval: 0,
      messages_in_view_interval: 0,
      messages_in_view: [] as Message[],
      selected_message_types: [],
      detailed_message: null as (null | Message),
      message_filter: '',
    }
  },
  computed: {
    filtered_messages(): string[] {
      try {
        return this.message_types.filter(
          (name: string) => name.toLowerCase().includes(this.message_filter.toLowerCase().trim()),
        )
      } catch {
        return this.message_types
      }
    },
  },
  mounted() {
    this.setupWs()
  },
  beforeDestroy() {
    clearInterval(this.message_type_interval)
    clearInterval(this.messages_in_view_interval)
  },
  methods: {
    update_messages_in_view() {
      this.messages_in_view = this.message_table.get(this.selected_message_types)
    },
    showDetailed(message: Message) {
      this.detailed_message = message
    },
    setupWs() {
      this.messages_in_view_interval = setInterval(() => this.update_messages_in_view(), 500)
      this.message_type_interval = setInterval(() => { this.message_types = this.message_table.getTypes() }, 1000)
      mavlink2rest.startListening('').setCallback((receivedMessage) => {
        this.message_table.add(receivedMessage)
      }).setFrequency(0)
    },
  },
})
</script>
<style>
.height-limited {
  overflow-y: auto;
  max-height: 700px;
}
</style>
