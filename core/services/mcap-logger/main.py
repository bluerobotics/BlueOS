import json
import time
import zenoh
from mcap.writer import Writer
from typing import Dict, Any, Optional

channel_map: Dict[str, int] = {}
schema_map: Dict[str, int] = {}

def get_schema_type(value: Any) -> str:
    """Determine the JSON schema type for a value."""
    if value is None:
        return "null"
    elif isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "number"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "string"
    return "string"  # default to string for unknown types

def create_schema(data: dict) -> dict:
    """Create a JSON schema from a data dictionary."""
    schema = {
        "type": "object",
        "properties": {},
        "additionalProperties": True
    }

    for key, value in data.items():
        try:
            if value is None:
                schema["properties"][key] = {
                    "type": ["null", "string"],
                    "description": f"Field {key}"
                }
            elif isinstance(value, dict):
                schema["properties"][key] = create_schema(value)
            else:
                schema["properties"][key] = {
                    "type": get_schema_type(value),
                    "description": f"Field {key}"
                }
        except Exception as e:
            print(f"Warning: Error creating schema for field {key}: {e}")
            # Add a generic string type for problematic fields
            schema["properties"][key] = {
                "type": "string",
                "description": f"Field {key} (error in schema creation)"
            }

    return schema

def process_value(value: Any) -> Any:
    """Process a value for MCAP storage."""
    try:
        if value is None:
            return None
        if isinstance(value, dict):
            return json.dumps(value)
        return value
    except Exception as e:
        print(f"Warning: Error processing value: {e}")
        return str(value)  # Fallback to string representation

def main(conf: zenoh.Config, key: str):
    # initiate logging
    zenoh.init_log_from_env_or("error")

    print("Opening session...")
    with zenoh.open(conf) as session:
        print(f"Declaring Subscriber on '{key}'...")

        with open("zenoh_dump.mcap", "wb") as f:
            writer = Writer(f)
            writer.start()

            def listener(sample: zenoh.Sample):
                try:
                    data = json.loads(sample.payload.to_string())
                    if not isinstance(data, dict):
                        print(f"Warning: Received non-dict data: {data}")
                        return
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    return
                except Exception as e:
                    print(f"Unexpected error processing message: {e}")
                    return

                topic = str(sample.key_expr)

                # Create or update schema
                if topic not in schema_map:
                    try:
                        schema = create_schema(data)
                        schema_id = writer.register_schema(
                            name=f"json_{topic}",
                            encoding="jsonschema",
                            data=json.dumps(schema).encode()
                        )
                        schema_map[topic] = schema_id
                    except Exception as e:
                        print(f"Error creating schema for {topic}: {e}")
                        return

                # Register or get channel
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
                    print(f"Error registering channel for {topic}: {e}")
                    return

                # Process and write message
                try:
                    timestamp = int(time.time_ns())

                    writer.add_message(
                        channel_id=channel_id,
                        log_time=timestamp,
                        publish_time=timestamp,
                        data=json.dumps(data).encode("utf-8")
                    )
                except Exception as e:
                    print(f"Error writing message for {topic}: {e}")

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
    parser.add_argument(
        "--key",
        "-k",
        dest="key",
        default="**",
        type=str,
        help="The key expression to subscribe to.",
    )

    args = parser.parse_args()
    conf = zenoh.Config()

    main(conf, args.key)
