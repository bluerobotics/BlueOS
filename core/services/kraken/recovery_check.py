from recovery import (
    LABEL_IDENTIFIER,
    LABEL_NAME,
    LABEL_PERMISSIONS,
    container_name_for,
    recovered_extension_from_inspect,
    split_image_name,
    stamp_extension_labels,
)


def check_split_image_name() -> None:
    assert split_image_name("bluerobotics/cockpit:v1.18.2") == ("bluerobotics/cockpit", "v1.18.2")
    assert split_image_name("public.ecr.aws/blueos/bcloud-agent:2026-02-11") == (
        "public.ecr.aws/blueos/bcloud-agent",
        "2026-02-11",
    )
    assert split_image_name("localhost:5000/foo/bar:tag") == ("localhost:5000/foo/bar", "tag")
    assert split_image_name("sha256:abc") is None
    assert split_image_name("") is None


def check_recover_from_labels() -> None:
    inspect = {
        "Name": "/extension-blueroboticscockpitv1182",
        "Config": {
            "Image": "bluerobotics/cockpit:v1.18.2",
            "Labels": {
                LABEL_IDENTIFIER: "bluerobotics.cockpit",
                LABEL_NAME: "Cockpit",
                LABEL_PERMISSIONS: '{"ExposedPorts":{"8000/tcp":{}}}',
            },
        },
    }
    recovered = recovered_extension_from_inspect(inspect)
    assert recovered is not None
    assert recovered["identifier"] == "bluerobotics.cockpit"
    assert recovered["name"] == "Cockpit"
    assert recovered["docker"] == "bluerobotics/cockpit"
    assert recovered["tag"] == "v1.18.2"
    assert recovered["enabled"] is True
    assert recovered["permissions"] == '{"ExposedPorts":{"8000/tcp":{}}}'


def check_recover_unlabeled_uses_docker_and_catalog() -> None:
    inspect = {
        "Name": "/extension-publicecrawsblueosbcloudagent20260211",
        "Config": {
            "Image": "public.ecr.aws/blueos/bcloud-agent:2026-02-11",
            "Labels": {"internal_id": "major_tom"},
            "ExposedPorts": None,
        },
        "HostConfig": {
            "NetworkMode": "host",
            "Privileged": True,
            "Binds": ["/var/logs:/var/logs"],
            "ExtraHosts": ["blueos:host-gateway"],
        },
    }
    unlabeled = recovered_extension_from_inspect(inspect)
    assert unlabeled is not None
    assert unlabeled["identifier"] == "public.ecr.aws.blueos.bcloud-agent"
    assert unlabeled["name"] == "bcloud-agent"
    assert "host" in unlabeled["permissions"]

    cataloged = recovered_extension_from_inspect(
        inspect, {"public.ecr.aws/blueos/bcloud-agent": ("blueos.major_tom", "major_tom")}
    )
    assert cataloged is not None
    assert cataloged["identifier"] == "blueos.major_tom"
    assert cataloged["name"] == "major_tom"


def check_skip_when_container_name_does_not_match_image() -> None:
    inspect = {
        "Name": "/extension-someoneelse",
        "Config": {"Image": "bluerobotics/cockpit:v1.18.2", "Labels": {}},
    }
    assert recovered_extension_from_inspect(inspect) is None
    assert container_name_for("bluerobotics/cockpit", "v1.18.2") == "extension-blueroboticscockpitv1182"


def check_stamp_extension_labels_merges() -> None:
    config = {"Labels": {"keep": "me"}}
    stamp_extension_labels(config, "bluerobotics.cockpit", "Cockpit", "{}", "")
    assert config["Labels"]["keep"] == "me"
    assert config["Labels"][LABEL_IDENTIFIER] == "bluerobotics.cockpit"


if __name__ == "__main__":
    check_split_image_name()
    check_recover_from_labels()
    check_recover_unlabeled_uses_docker_and_catalog()
    check_skip_when_container_name_does_not_match_image()
    check_stamp_extension_labels_merges()
    print("ok")
