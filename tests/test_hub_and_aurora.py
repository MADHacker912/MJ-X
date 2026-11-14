"""
tests.test_hub_and_aurora — Unit tests for Visual Hub (Project MIRROR) and Mobile Sync (Project AURORA).
"""

import json
from mjx.hub import VisualHubController, WidgetRegistry
from mjx.aurora import AuroraPairingManager, AuroraSyncProtocol


def test_visual_hub_widget_lifecycle_and_subscription():
    hub = VisualHubController()
    dispatched = []

    hub.subscribe(lambda w: dispatched.append(w.widget_id))

    # Publish an update
    w = hub.publish_widget_update(
        widget_id="sys_status",
        widget_type="status_card",
        title="System Status",
        data={"cpu": 12.5, "mem": 45.0},
    )
    assert w.widget_id == "sys_status"
    assert len(dispatched) == 1
    assert dispatched[0] == "sys_status"

    # Workspace snapshot
    snap = hub.get_workspace_snapshot()
    assert len(snap["widgets"]) == 1
    assert snap["widgets"][0]["title"] == "System Status"


def test_aurora_pairing_pin_and_token_verification():
    mgr = AuroraPairingManager(pin_ttl_secs=10.0)

    session = mgr.generate_pairing_code("pixel_8_pro")
    assert len(session.pin_code) == 6
    assert session.is_authenticated is False

    # Wrong PIN
    res_bad = mgr.verify_pin("pixel_8_pro", "000000" if session.pin_code != "000000" else "111111")
    assert res_bad is None

    # Correct PIN
    token = mgr.verify_pin("pixel_8_pro", session.pin_code)
    assert token is not None
    assert mgr.is_token_valid(token) is True


def test_aurora_sync_protocol_telemetry():
    proto = AuroraSyncProtocol()

    telemetry = json.dumps({
        "device_id": "pixel_8_pro",
        "battery": 88,
        "charging": True,
        "wifi": True,
        "clipboard": "https://github.com",
    })

    state = proto.parse_mobile_telemetry(telemetry)
    assert state is not None
    assert state.battery_level == 88
    assert state.is_charging is True
    assert state.clipboard_content == "https://github.com"

    notif_json = proto.build_push_notification("Meeting Alert", "Call starts in 5 minutes")
    parsed_notif = json.loads(notif_json)
    assert parsed_notif["title"] == "Meeting Alert"
