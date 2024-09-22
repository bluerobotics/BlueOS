import re


def parse_nginx_file(filepath: str) -> dict[int, str]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        # Define pattern for extracting location blocks
        location_block_pattern = re.compile(r"location\s+(?P<location>/[\w-]+)\s*{(?P<block_content>[^}]+)}", re.DOTALL)

        # Pattern for extracting proxy_pass directive
        proxy_pass_pattern = re.compile(r"proxy_pass\s.*:(?P<port>\d+).*;")
        location_blocks = location_block_pattern.finditer(content)
        result = {}
        for match in location_blocks:
            location = match.group("location")
            block_content = match.group("block_content")

            proxy_pass_match = proxy_pass_pattern.search(block_content)
            if proxy_pass_match:
                proxy_port = int(proxy_pass_match.group("port"))
                result[proxy_port] = location

        return result
