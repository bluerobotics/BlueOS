import pathlib
import json

def migrate(settings_file: pathlib.Path) -> None:
    with open(settings_file, 'r', encoding='utf-8') as file:
        content = json.load(file)

    attributes = content['attributes']
    old_endpoints = attributes['endpoints']
    new_endpoints = []
    for endpoint in old_endpoints:
        endpoint['owner'] = 'undefined_owner'
        new_endpoints.append(endpoint)
    content['attributes']['endpoints'] = new_endpoints
    content['settings_version'] = 2

    with open(settings_file, 'w', encoding='utf-8') as file:
        json.dump(content, file, indent=2)
