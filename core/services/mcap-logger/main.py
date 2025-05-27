import time
import json
import zenoh
import logging
from genson import SchemaBuilder
from mcap.writer import Writer
from typing import Dict, Any, Optional
from foxglove import Channel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

channel_map: Dict[str, int] = {}
schema_map: Dict[str, int] = {}

def create_schema(data: dict) -> Optional[bytes]:
    """Create a JSON schema from the given data."""
    try:
        builder = SchemaBuilder()
        builder.add_object(data)
        return json.dumps(builder.to_schema()).encode()
    except Exception as e:
        logger.error(f"Failed to create schema: {e}")
        return None

def validate_data(data: Any) -> bool:
    """Validate if the data is in the expected format."""
    return isinstance(data, dict) and len(data) > 0

def main(conf: zenoh.Config, key: str):
    zenoh.init_log_from_env_or("error")
    logger.info("Opening session...")

    with zenoh.open(conf) as session:
        logger.info(f"Declaring Subscriber on '{key}'...")

        with open("zenoh_dump.mcap", "wb") as f:
            writer = Writer(f)
            writer.start()

            def listener(sample: zenoh.Sample):
                topic = str(sample.key_expr)
                logger.debug(f"Received message on topic: {topic}")

                try:
                    data = json.loads(sample.payload.to_string())
                    if not validate_data(data):
                        # logger.warning(f"Invalid data format for topic {topic}")
                        return
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON for topic {topic}: {e}")
                    return
                except Exception as e:
                    logger.error(f"Unexpected error processing message for topic {topic}: {e}")
                    return

                # Handle schema registration
                if topic not in schema_map:
                    try:
                        if topic.endswith("/log"):
                            channel = Channel(topic, message_encoding="json")
                            schema_id = writer.register_schema(
                                name="foxglove.Log",
                                encoding="jsonschema",
                                data=json.dumps({"type": "object"}).encode()
                            )
                            channel_id = writer.register_channel(
                                schema_id=schema_id,
                                topic=topic,
                                message_encoding="json"
                            )
                            channel_map[topic] = channel_id
                            schema_map[topic] = schema_id
                            logger.info(f"Registered Foxglove Log schema for topic: {topic}")
                        else:
                            schema_data = create_schema(data)
                            if schema_data is None:
                                logger.error(f"Failed to create schema for topic: {topic}")
                                return

                            schema_id = writer.register_schema(
                                name=f"json_{topic}",
                                encoding="jsonschema",
                                data=schema_data
                            )
                            schema_map[topic] = schema_id
                            logger.info(f"Registered custom schema for topic: {topic}")
                    except Exception as e:
                        logger.error(f"Schema registration error for topic {topic}: {e}")
                        return

                # Handle channel registration
                try:
                    if topic not in channel_map and not topic.endswith("/log"):
                        channel_id = writer.register_channel(
                            schema_id=schema_map[topic],
                            topic=topic,
                            message_encoding="json"
                        )
                        channel_map[topic] = channel_id
                        logger.info(f"Registered channel for topic: {topic}")
                    else:
                        channel_id = channel_map[topic]
                except Exception as e:
                    logger.error(f"Channel registration error for topic {topic}: {e}")
                    return

                # Write message
                try:
                    ts = int(time.time_ns())
                    writer.add_message(
                        channel_id=channel_id,
                        log_time=ts,
                        publish_time=ts,
                        data=json.dumps(data).encode()
                    )
                    logger.debug(f"Successfully wrote message for topic: {topic}")
                except Exception as e:
                    logger.error(f"Failed to write message for topic {topic}: {e}")

            session.declare_subscriber(key, listener)

            logger.info("Press CTRL-C to quit...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\nShutting down...")
            finally:
                writer.finish()
                logger.info("MCAP writer finished")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="mcap_logger", description="MCAP logger for zenoh messages")
    parser.add_argument("--key", "-k", default="**", type=str, help="The key expression to subscribe to.")
    parser.add_argument("--log-level", "-l", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                      help="Set the logging level")
    args = parser.parse_args()

    # Set logging level from command line argument
    logger.setLevel(getattr(logging, args.log_level))

    conf = zenoh.Config()
    conf.insert_json5("mode", '"peer"')

    main(conf, args.key)
