import time
import json
import zenoh
from genson import SchemaBuilder
from mcap.writer import Writer
from typing import Dict, Any

channel_map: Dict[str, int] = {}
schema_map: Dict[str, int] = {}

def create_schema(data: dict) -> bytes:
    builder = SchemaBuilder()
    builder.add_object(data)
    return json.dumps(builder.to_schema()).encode()

def main(conf: zenoh.Config, key: str):
    zenoh.init_log_from_env_or("error")

    print("Opening session...")
    with zenoh.open(conf) as session:
        print(f"Declaring Subscriber on '{key}'...")

        with open("zenoh_dump.mcap", "wb") as f:
            writer = Writer(f)
            writer.start()

            def listener(sample: zenoh.Sample):
                topic = str(sample.key_expr)
                print(topic)
                try:
                    data = json.loads(sample.payload.to_string())
                    if not isinstance(data, dict):
                        return
                except Exception:
                    return

                if topic not in schema_map:
                    try:
                        schema_data = create_schema(data)
                        schema_id = writer.register_schema(
                            name=f"json_{topic}",
                            encoding="jsonschema",
                            data=schema_data
                        )
                        schema_map[topic] = schema_id
                    except Exception as e:
                        print(f"Schema error [{topic}]: {e}")
                        return

                try:
                    if topic not in channel_map:
                        channel_id = writer.register_channel(
                            schema_id=schema_map[topic],
                            topic=topic,
                            message_encoding="json"
                        )
                        channel_map[topic] = channel_id
                    else:
                        channel_id = channel_map[topic]
                except Exception as e:
                    print(f"Channel error [{topic}]: {e}")
                    return

                try:
                    ts = int(time.time_ns())
                    writer.add_message(
                        channel_id=channel_id,
                        log_time=ts,
                        publish_time=ts,
                        data=json.dumps(data).encode()
                    )
                except Exception as e:
                    print(f"Write error [{topic}]: {e}")

            session.declare_subscriber(key, listener)

            print("Press CTRL-C to quit...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down...")
            finally:
                writer.finish()

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="mcap_logger", description="MCAP logger for zenoh messages")
    parser.add_argument("--key", "-k", default="**", type=str, help="The key expression to subscribe to.")
    args = parser.parse_args()
    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')

    main(conf, args.key)
